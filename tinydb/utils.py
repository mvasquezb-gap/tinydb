import yaml

def load_config(stream):
    return yaml.safe_load(stream)
