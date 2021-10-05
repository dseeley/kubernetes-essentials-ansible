#!/usr/bin/env python

from ansible.utils.display import Display
from ansible import constants as C
from ansible.module_utils._text import to_native, to_text
from ansible.template import AnsibleUndefined

display = Display()


# Convert a YAML object containing $ANSIBLE_VAULT to a yaml multiline string beginning "!vault |".  Useful to output vaulted yaml to file without decrypting.
def to_yaml_vaulted(yamlobj):
    import yaml
    from ansible.parsing.yaml.objects import AnsibleUnicode, AnsibleVaultEncryptedUnicode
    from ansible.utils.unsafe_proxy import AnsibleUnsafeText

    vault_tagstr = u'!vault'

    def str_presenter(dumper, data):
        if data.startswith('$ANSIBLE_VAULT'):
            return dumper.represent_scalar(vault_tagstr, data, style='|')
        else:
            if len(data.splitlines()) > 1:
                return dumper.represent_scalar(u'tag:yaml.org,2002:str', data, style='|')
            else:
                return dumper.represent_scalar(u'tag:yaml.org,2002:str', data)

    yaml.add_representer(AnsibleVaultEncryptedUnicode, lambda dumper, data: dumper.represent_scalar(vault_tagstr, data._ciphertext.decode('utf-8'), style='|'))
    yaml.add_representer(AnsibleUnsafeText, str_presenter)
    yaml.add_representer(AnsibleUnicode, str_presenter)
    yaml.add_representer(str, str_presenter)
    yaml.representer.SafeRepresenter.add_representer(str, str_presenter)    # to use with safe_dump

    return (yaml.dump(yamlobj, width=4096, encoding='utf-8')).decode('utf-8')


# Convert a YAML string with the "!vault" tag to a plain (not-decrypted) yaml Object (without the tag).  Useful for loading vaulted string as encrypted yaml.
def from_yaml_vaulted(yamlstr):
    import yaml

    def vault_constructor(loader, node):
        value = loader.construct_scalar(node)
        return (value)

    yaml.add_constructor(u'!vault', vault_constructor)

    return yaml.load(yamlstr, Loader=yaml.FullLoader)


class FilterModule(object):
    def filters(self):
        return {
            'from_yaml_vaulted': from_yaml_vaulted,
            'to_yaml_vaulted': to_yaml_vaulted
        }