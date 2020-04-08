# mapbox2qgis

Convert vector tile styles from Mapbox GL to QGIS (using the new vector tile layer).

This is still in the very early stages and supporting just a subset of styling. More to come later...

How to use: open QGIS, open Python console in QGIS and load the conversion script (make sure to use the correct path):

```
exec(open('/path/to/mapbox2qgis/mapbox2qgis.py'.encode('utf-8')).read())
```

Then you can select a vector tile layer and run the conversion:

```
iface.activeLayer().setRenderer(parse_json('/path/to/my/style.json'))
```
