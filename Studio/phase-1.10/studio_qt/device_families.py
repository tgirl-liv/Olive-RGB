"""Known controller targets; metadata only, safe to import without BLE."""
LOTUS='LotusLamp Corner Lamp'
LEDBLE='LEDBLE Strip'
FAMILIES=(LOTUS,LEDBLE)


def identity_for(family):
    if family==LOTUS:return {'name':'MELK-OA10   7F','address':'BE:28:87:00:08:7F'}
    if family==LEDBLE:return {'name':'LEDBLE-00-0806'}
    raise ValueError('Unknown controller family')
