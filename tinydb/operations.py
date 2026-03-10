def copy_field(doc, from_key, to_key):
    if from_key in doc:
        doc[to_key] = doc[from_key]
    return doc
