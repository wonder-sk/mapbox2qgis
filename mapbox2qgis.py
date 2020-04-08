"""
Parser of Mapbox GL styles for QGIS vector tile layer implementation

Copyright 2020 Martin Dobias

Licensed under the terms of MIT license (see LICENSE file)
"""

import json
from PyQt5.QtGui import QColor
from qgis.core import QgsSymbol, QgsWkbTypes, QgsVectorTileBasicRenderer, QgsVectorTileBasicRendererStyle


def parse_color(json_color):
    """
    Parse color in one of these supported formats:
      - #fff or #ffffff
      - hsl(30, 19%, 90%) or hsla(30, 19%, 90%, 0.4)
      - rgb(10, 20, 30) or rgba(10, 20, 30, 0.5)
    """
    if json_color[0] == '#':
        return QColor(json_color)
    elif json_color.startswith('hsla'):
        x = json_color[5:-1]
        lst = x.split(',')
        assert len(lst) == 4 and lst[1].endswith('%') and lst[2].endswith('%')
        hue = int(lst[0])
        sat = float(lst[1][:-1]) / 100. * 255
        lig = float(lst[2][:-1]) / 100. * 255
        alpha = float(lst[3]) * 255
        #print(hue,sat,lig,alpha)
        return QColor.fromHsl(hue, sat, lig, alpha)
    elif json_color.startswith('hsl'):
        x = json_color[4:-1]
        lst = x.split(',')
        assert len(lst) == 3 and lst[1].endswith('%') and lst[2].endswith('%')
        hue = int(lst[0])
        sat = float(lst[1][:-1]) / 100. * 255
        lig = float(lst[2][:-1]) / 100. * 255
        #print(hue,sat,lig)
        return QColor.fromHsl(hue, sat, lig)
    elif json_color.startswith('rgba'):
        x = json_color[5:-1]
        lst = x.split(',')
        assert len(lst) == 4
        return QColor(int(lst[0]), int(lst[1]), int(lst[2]), float(lst[3]) * 255)
    elif json_color.startswith('rgb'):
        x = json_color[4:-1]
        lst = x.split(',')
        assert len(lst) == 3
        return QColor(int(lst[0]), int(lst[1]), int(lst[2]))
    else:
        raise ValueError("unknown color syntax", json_color)


def parse_key(json_key):
    if json_key == '$type':
        return "_geom_type"
    return '"{}"'.format(json_key)  # TODO: better escaping


def parse_value(json_value):
    if isinstance(json_value, list):
        return parse_expression(json_value)
    elif isinstance(json_value, str):
        return "'{}'".format(json_value)  # TODO: better escaping
    elif isinstance(json_value, int):
        return str(json_value)
    else:
        print(type(json_value), isinstance(json_value, list), json_value)
        return "?"


def parse_expression(json_expr):
    """ Parses expression into QGIS expression string """
    op = json_expr[0]
    if op == 'all':
        lst = [parse_value(v) for v in json_expr[1:]]
        return "({})".format(") AND (".join(lst))
    elif op == 'any':
        lst = [parse_value(v) for v in json_expr[1:]]
        return "({})".format(") OR (".join(lst))
    elif op in ("==", "!=", ">=", ">", "<=", "<"):
        if op == "==":
            op = "="   # we use single '=' not '=='
        return "{} {} {}".format(parse_key(json_expr[1]), op, parse_value(json_expr[2]))
    elif op == 'has':
        return parse_key(json_expr[1]) + " IS NOT NULL"
    elif op == '!has':
        return parse_key(json_expr[1]) + " IS NULL"
    elif op == 'in' or op == '!in':
        key = parse_key(json_expr[1])
        lst = [parse_value(v) for v in json_expr[2:]]
        if op == 'in':
            return "{} IN ({})".format(key, ", ".join(lst))
        else:  # not in
            return "({} IS NULL OR {} NOT IN ({}))".format(key, key, ", ".join(lst))

    raise ValueError(json_expr)


def parse_fill_layer(json_layer):
    json_paint = json_layer['paint']

    if 'fill-color' not in json_paint:
        print("skipping fill without fill-color", json_paint)
        return

    json_fill_color = json_paint['fill-color']
    if not isinstance(json_fill_color, str):
        print("skipping non-string color", json_fill_color)
        return

    fill_color = parse_color(json_fill_color)

    fill_outline_color = fill_color

    if 'fill-outline-color' in json_paint:
        json_fill_outline_color = json_paint['fill-outline-color']
        if isinstance(json_fill_outline_color, str):
            fill_outline_color = parse_color(json_fill_outline_color)
        else:
            print("skipping non-string color", json_fill_outline_color)

    fill_opacity = 1.0
    if 'fill-opacity' in json_paint:
        json_fill_opacity = json_paint['fill-opacity']
        if isinstance(json_fill_opacity, (float, int)):
            fill_opacity = float(json_fill_opacity)
        else:
            print("skipping non-float opacity", json_fill_opacity)

    sym = QgsSymbol.defaultSymbol(QgsWkbTypes.PolygonGeometry)
    fill_symbol = sym.symbolLayer(0)
    fill_symbol.setColor(fill_color)
    fill_symbol.setStrokeColor(fill_outline_color)
    sym.setOpacity(fill_opacity)

    st = QgsVectorTileBasicRendererStyle()
    st.setGeometryType(QgsWkbTypes.PolygonGeometry)
    st.setSymbol(sym)
    return st


def parse_line_layer(json_layer):
    json_paint = json_layer['paint']

    if 'line-color' not in json_paint:
        print("skipping line without line-color", json_paint)
        return

    json_line_color = json_paint['line-color']
    if not isinstance(json_line_color, str):
        print("skipping non-string color", json_line_color)
        return

    line_color = parse_color(json_line_color)

    sym = QgsSymbol.defaultSymbol(QgsWkbTypes.LineGeometry)
    line_symbol = sym.symbolLayer(0)
    line_symbol.setColor(line_color)

    st = QgsVectorTileBasicRendererStyle()
    st.setGeometryType(QgsWkbTypes.LineGeometry)
    st.setSymbol(sym)
    return st


def parse_layers(json_layers):
    """ Parse list of layers from JSON and return QgsVectorTileBasicRenderer """

    styles = []

    for json_layer in json_layers:
        layer_type = json_layer['type']
        if layer_type == 'background': continue   # TODO: parse background color
        style_id = json_layer['id']
        layer_name = json_layer['source-layer']
        min_zoom = json_layer['minzoom'] if 'minzoom' in json_layer else -1
        max_zoom = json_layer['maxzoom'] if 'maxzoom' in json_layer else -1

        filter_expr = ''
        if 'filter' in json_layer:
          filter_expr = parse_expression(json_layer['filter'])

        if layer_type == 'fill':
            st = parse_fill_layer(json_layer)
        elif layer_type == 'line':
            st = parse_line_layer(json_layer)
        else:
            print("skipping unknown layer type", layer_type)
            continue

        if st:
            st.setStyleName(style_id)
            st.setLayerName(layer_name)
            st.setFilterExpression(filter_expr)
            st.setMinZoomLevel(min_zoom)
            st.setMaxZoomLevel(max_zoom)
            styles.append(st)

        #print(style_id, layer_type, layer_name, min_zoom, max_zoom, filter_expr)

    renderer = QgsVectorTileBasicRenderer()
    renderer.setStyles(styles)
    return renderer



def parse_json(filename='/home/martin/tmp/mvt-plugin-layer/style.json'):
    file_style = open(filename, 'r')
    json_str = file_style.read()

    json_data = json.loads(json_str)
    json_layers = json_data['layers']
    return parse_layers(json_layers)
