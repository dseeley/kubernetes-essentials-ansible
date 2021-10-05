# kubernetes-essentials-ansible
An Ansible role to deploy the essentials of a highly available Kubernetes cluster. Includes in-cluster apiserver and ingress controller loadbalancing, dns and flannel.

It is somewhat based on the canonical [kelseyhightower/kubernetes-the-hard-way](https://github.com/kelseyhightower/kubernetes-the-hard-way) runbooks, albeit completely Ansible-ised.
+ In common, it downloads and runs the controller componenets (apiserver, controller-manager and scheduler) _outside_ the cluster as systemd services.  Similarly, for kubelets on the worker nodes.  
+ However:
  + etcd runs in separate VMs
  + The apiservers uses keepalived (with IPVS real-servers on the same hosts as the directors).  This means the host that is owner of the VIP receives the request, but hands it off in the kernel for processing by one of the apiservers.
  + [haproxy-ingress](https://haproxy-ingress.github.io/) is used as an ingress controller.  It runs as a daemonset on special _node-edge_ worker nodes with hostNetwork.

It supports only (at present) non-cloud infrastructure.  

This project is designed to operate using [clusterverse](https://github.com/dseeley/clusterverse) to provision and manage the base VM infrastructure.  Please see the [README.md](https://github.com/dseeley/clusterverse/blob/master/README.md) there for instructions on deployment.  There is an [EXAMPLE](https://github.com/dseeley/kubernetes-essentials-ansible/tree/master/EXAMPLE) folder that can be copied as a new project root.

## Contributing
Contributions are welcome and encouraged.  Please see [CONTRIBUTING.md](https://github.com/dseeley/kubernetes-essentials-ansible/blob/master/CONTRIBUTING.md) for details.

## Requirements

### ESXi (free)
+ Username & password for a privileged user on an ESXi host
+ SSH must be enabled on the host
+ Set the `Config.HostAgent.vmacore.soap.maxSessionCount` variable to 0 to allow many concurrent tests to run.   
+ Set the `Security.SshSessionLimit` variable to max (100) to allow as many ssh sessions as possible.   

### DNS
DNS is optional.  If unset, no DNS names will be created.  If DNS is required, you will need a DNS zone delegated to one of the following:
+ nsupdate (e.g. bind9)
+ AWS Route53
+ Google Cloud DNS

Credentials to the DNS server will also be required. These are specified in the `cluster_vars` variable described below.


### Cluster Definition Variables
Clusters are defined as code within Ansible yaml files that are imported at runtime.  Because clusters are built from scratch on the localhost, the automatic Ansible `group_vars` inclusion cannot work with anything except the special `all.yml` group (actual `groups` need to be in the inventory, which cannot exist until the cluster is built).  The `group_vars/all.yml` file is instead used to bootstrap _merge_vars_.  Please see the full documentation in the main [clusterverse/README.md](https://github.com/dseeley/clusterverse/blob/master/README.md#cluster-definition-variables)


---
## Usage
**kubernetes-essentials-ansible** is an Ansible _role_, and as such must be imported into your \<project\>/roles directory.  There is a full-featured example in the [/EXAMPLE](https://github.com/dseeley/kubernetes-essentials-ansible/tree/master/EXAMPLE) subdirectory.

To import the role into your project, create a [`requirements.yml`](https://github.com/dseeley/clusterverse/blob/master/EXAMPLE/requirements.yml) file containing:
```
roles:
  - name: clusterverse
    src: https://github.com/dseeley/clusterverse
    version: master          ## branch, hash, or tag 

  - name: kubernetes-essentials-ansible
    src: https://github.com/dseeley/kubernetes-essentials-ansible
    version: master          ## branch, hash, or tag 
```
+ If you use a `cluster.yml` file similar to the example found in [EXAMPLE/cluster.yml](https://github.com/dseeley/kubernetes-essentials-ansible/blob/master/EXAMPLE/cluster.yml), clusterverse will be installed from Ansible Galaxy _automatically_ on each run of the playbook.

+ To install it manually: `ansible-galaxy install -r requirements.yml -p /<project>/roles/`


### Invocation

_**For full clusterverse invocation examples and command-line arguments, please see the [example README.md](https://github.com/dseeley/clusterverse/blob/master/EXAMPLE/README.md)**_

The role is designed to run in two modes:
#### Deploy (also performs _scaling_ and _repairs_)
+ A playbook based on the [cluster.yml example](https://github.com/dseeley/clusterverse/tree/master/EXAMPLE/cluster.yml) will be needed.
+ The `cluster.yml` sub-role idempotently deploys a cluster from the config defined above (if it is run again (with no changes to variables), it will do nothing).  If the cluster variables are changed (e.g. add a host), the cluster will reflect the new variables (e.g. a new host will be added to the cluster.  Note: it _will not remove_ nodes, nor, usually, will it reflect changes to disk volumes - these are limitations of the underlying cloud modules).


#### Redeploy
+ A playbook based on the [redeploy.yml example](https://github.com/dseeley/clusterverse/tree/master/EXAMPLE/redeploy.yml) will be needed.
+ The `redeploy.yml` sub-role will completely redeploy the cluster; this is useful for example to upgrade the underlying operating system version.
+ It supports `canary` deploys.  The `canary` extra variable must be defined on the command line set to one of: `start`, `finish`, `filter`, `none` or `tidy`.
+ It contains callback hooks:
  + `mainclusteryml`: This is the name of the deployment playbook.  It is called to deploy nodes for the new cluster, or to rollback a failed deployment.  It should be set to the value of the primary _deploy_ playbook yml (e.g. `cluster.yml`)
  + `predeleterole`: This is the name of a role that should be called prior to deleting VMs; it is used for example to eject nodes from a Couchbase cluster.  It takes a list of `hosts_to_remove` VMs. 
+ It supports pluggable redeployment schemes.  The following are provided:
  + **_scheme_rmvm_rmdisk_only**
      + This is a very basic rolling redeployment of the cluster.  
      + _Supports redploying to bigger, but not smaller clusters_
      + **It assumes a resilient deployment (it can tolerate one node being deleted from the cluster). There is _no rollback_ in case of failure.**
      + For each node in the cluster:
        + Run `predeleterole`
        + Delete/ terminate the node (note, this is _irreversible_).
        + Run the main cluster.yml (with the same parameters as for the main playbook), which forces the missing node to be redeployed (the `cluster_suffix` remains the same).
      + If `canary=start`, only the first node is redeployed.  If `canary=finish`, only the remaining (non-first), nodes are redeployed.  If `canary=none`, all nodes are redeployed.
      + If `canary=filter`, you must also pass `canary_filter_regex=regex` where `regex` is a pattern that matches the hostnames of the VMs that you want to target.
      + If the process fails at any point:
        + No further VMs will be deleted or rebuilt - the playbook stops. 
  + **_scheme_addnewvm_rmdisk_rollback**
      + _Supports redploying to bigger or smaller clusters_
      + For each node in the cluster:
        + Create a new VM
        + Run `predeleterole` on the previous node
        + Shut down the previous node.
      + If `canary=start`, only the first node is redeployed.  If `canary=finish`, only the remaining (non-first), nodes are redeployed.  If `canary=none`, all nodes are redeployed.
      + If `canary=filter`, you must also pass `canary_filter_regex=regex` where `regex` is a pattern that matches the hostnames of the VMs that you want to target.
      + If the process fails for any reason, the old VMs are reinstated, and any new VMs that were built are stopped (rollback)
      + To delete the old VMs, either set '-e canary_tidy_on_success=true', or call redeploy.yml with '-e canary=tidy'
  + **_scheme_addallnew_rmdisk_rollback**
      + _Supports redploying to bigger or smaller clusters_
      + If `canary=start` or `canary=none`
        + A full mirror of the cluster is deployed.
      + If `canary=finish` or `canary=none`:
          + `predeleterole` is called with a list of the old VMs.
          + The old VMs are stopped.
      + If `canary=filter`, an error message will be shown is this scheme does not support it.
      + If the process fails for any reason, the old VMs are reinstated, and the new VMs stopped (rollback)
      + To delete the old VMs, either set '-e canary_tidy_on_success=true', or call redeploy.yml with '-e canary=tidy'
  + **_scheme_rmvm_keepdisk_rollback**
      + Redeploys the nodes one by one, and moves the secondary (non-root) disks from the old to the new (note, only non-ephemeral disks can be moved).
      + _Cluster node topology must remain identical.  More disks may be added, but none may change or be removed._
      + **It assumes a resilient deployment (it can tolerate one node being removed from the cluster).**
      + For each node in the cluster:
        + Run `predeleterole`
        + Stop the node
        + Detach the disks from the old node
        + Run the main cluster.yml to create a new node
        + Attach disks to new node
      + If `canary=start`, only the first node is redeployed.  If `canary=finish`, only the remaining (non-first), nodes are replaced.  If `canary=none`, all nodes are redeployed.
      + If `canary=filter`, you must also pass `canary_filter_regex=regex` where `regex` is a pattern that matches the hostnames of the VMs that you want to target.
      + If the process fails for any reason, the old VMs are reinstated (and the disks reattached to the old nodes), and the new VMs are stopped (rollback)
      + To delete the old VMs, either set '-e canary_tidy_on_success=true', or call redeploy.yml with '-e canary=tidy'
      + (Azure functionality coming soon)
