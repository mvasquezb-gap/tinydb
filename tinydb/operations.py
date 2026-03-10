def get_field(doc, key):
    try:
        return doc[key]
    except KeyError:
        pass
    return None
