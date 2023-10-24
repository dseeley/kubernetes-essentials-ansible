# kubernetes-essentials-ansible
An Ansible role to deploy the essentials of a highly available Kubernetes cluster. Includes in-cluster apiserver and ingress controller loadbalancing, dns and flannel.

It was originally loosely based on the canonical [kelseyhightower/kubernetes-the-hard-way](https://github.com/kelseyhightower/kubernetes-the-hard-way) runbooks, but completely Ansible-ised, and not GCP-specific.
+ In common, it downloads and runs the controller componenets (apiserver, controller-manager and scheduler) _outside_ the cluster as systemd services.  Similarly, for kubelets on the worker nodes.  
+ However:
  + etcd runs in separate VMs
  + The apiserver nodes are load-balanced using cloud-specific tools:
    + **Libvirt** / **ESXi**: keepalived (with IPVS real-servers on the same hosts as the directors).  This means the host that is owner of the VIP receives the request, but hands it off in the kernel for processing by one of the apiservers.
    + **AWS**: Network load balancers, configured for internal load-balancing.  One per-zone for resilience.
  + [haproxy-ingress](https://haproxy-ingress.github.io/) is used as an ingress controller.  It runs as a daemonset on special _node-edge_ worker nodes with hostNetwork.

It supports (at present) AWS, libvirt(KVM/Qemu) and ESXi infrastructure.  

This project is designed to operate using [clusterverse](https://github.com/dseeley/clusterverse) to provision and manage the base VM infrastructure.  Please see the [README.md](https://github.com/dseeley/clusterverse/blob/master/README.md) there for instructions on deployment.  There is an [EXAMPLE](https://github.com/dseeley/kubernetes-essentials-ansible/tree/master/EXAMPLE) folder that can be copied as a new project root.

## Contributing
Contributions are welcome and encouraged.  Please see [CONTRIBUTING.md](https://github.com/dseeley/kubernetes-essentials-ansible/blob/master/CONTRIBUTING.md) for details.

## Requirements

It is only tested on Ubuntu 22.04 at present.

### libvirt (Qemu)
+ It is non-trivial to set up username/password access to a remote libvirt host, so we use an ssh key instead.
+ Your ssh user should be a member of the `libvirt` and `kvm` groups.
+ Store the config in `cluster_vars.libvirt`

### ESXi
+ Username & password for a privileged user on an ESXi host
+ SSH must be enabled on the host
+ Set the `Config.HostAgent.vmacore.soap.maxSessionCount` variable to 0 to allow many concurrent tests to run.   
+ Set the `Security.SshSessionLimit` variable to max (100) to allow as many ssh sessions as possible.   
+ You need a template VM.  [gold-img-build-esxi](https://github.com/dseeley/gold-img-build-esxi) can be used if needed.
+ DNS is optional.  If set, you will need a DNS server of either nsupdate (bind9), AWS route53 or GCP CloudDNS.
+ Store the config in `cluster_vars.esxi` 

### AWS
+ VPC and subnets configured
+ IAM role with access/secret key.
+ Route53 private Hosted zone (it probably could be run publicly, by setting `cluster_vars.assign_public_ip: true` and `cluster_vars.assign_public_ip: public`, but this would be highly insecure.
  + DNS is mandatory, because the NLBs do not provide a globally unique IP, and the APIservers need a load-balancer with either a single IP or a DNS name.


### Cluster Definition Variables
Clusters are defined as code within Ansible yaml files that are imported at runtime.  Because clusters are built from scratch on the localhost, the automatic Ansible `group_vars` inclusion cannot work with anything except the special `all.yml` group (actual `groups` need to be in the inventory, which cannot exist until the cluster is built).  The `group_vars/all.yml` file is instead used to bootstrap _merge_vars_, and the definitions are hierarchically defined in [cluster_defs](https://github.com/dseeley/kubernetes-essentials-ansible/tree/master/EXAMPLE/cluster_defs).  Please see the full documentation in the main [clusterverse/README.md](https://github.com/dseeley/clusterverse/blob/master/README.md#cluster-definition-variables)


---
## Usage
**kubernetes-essentials-ansible** is an Ansible _role_, and as such must be imported into your project's _/roles_ directory.  There is a full-featured example in the [/EXAMPLE](https://github.com/dseeley/kubernetes-essentials-ansible/tree/master/EXAMPLE) subdirectory.

To import the role into your project, create a [`requirements.yml`](https://github.com/dseeley/kubernetes-essentials-ansible/blob/master/EXAMPLE/requirements.yml) file containing:
```
roles:
  - name: clusterverse
    src: https://github.com/dseeley/clusterverse
    version: master          ## branch, hash, or tag 

  - name: kubernetes
    src: https://github.com/dseeley/kubernetes-essentials-ansible
    version: master          ## branch, hash, or tag 
```
+ If you use a `cluster.yml` file similar to the example found in [EXAMPLE/cluster.yml](https://github.com/dseeley/kubernetes-essentials-ansible/blob/master/EXAMPLE/cluster.yml), clusterverse will be installed from Ansible Galaxy _automatically_ on each run of the playbook.

+ To install it manually: `ansible-galaxy install -r requirements.yml -p ./roles`


### Invocation

_**For full clusterverse invocation examples and command-line arguments, please see the [example README.md](https://github.com/dseeley/clusterverse/blob/master/EXAMPLE/README.md)**_

The role is designed to run in two modes:
#### Deploy (also performs _up-scaling_ and _repairs_)
+ A playbook based on the [cluster.yml example](https://github.com/dseeley/clusterverse/tree/master/EXAMPLE/cluster.yml) will be needed.
+ The `cluster.yml` sub-role idempotently deploys a cluster from the config defined above (if it is run again (with no changes to variables), it will do nothing).  If the cluster variables are changed (e.g. add a host), the cluster will reflect the new variables (e.g. a new host will be added to the cluster.  Note: it _will not remove_ nodes, nor, usually, will it reflect changes to disk volumes - these are limitations of the underlying cloud modules).
+ Example:
```
    ansible-playbook cluster.yml -e cloud_type=libvirt -e region=dougalab -e buildenv=dev -e testapps=true
```

#### Redeploy
+ A playbook based on the [redeploy.yml example](https://github.com/dseeley/clusterverse/tree/master/EXAMPLE/redeploy.yml) will be needed.
+ The `redeploy.yml` sub-role will completely redeploy the cluster; this is useful for example to upgrade the underlying operating system version.
+ Please see the full [documentation](#https://github.com/dseeley/clusterverse#redeploy)
+ Example:
```
    ansible-playbook redeploy.yml -e canary=none -e cloud_type=esxifree -e clusterid=dougakube -e region=dougalab -e buildenv=dev -e testapps=true
  ```
