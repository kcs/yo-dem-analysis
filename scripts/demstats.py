# -*- coding: utf-8 -*-

"""
QGIS Processing algorithm to assess relative summit statistics
"""
__author__ = "dr. Kertész Csaba Zoltán"
__email__ = "csaba.kertesz@unitbv.ro"
__copyright__ = "Copyright 2022, dr. Kertész Csaba-Zoltán"
__license__ = "MIT"


from qgis.processing import alg
from qgis.core import (QgsProcessing,
                       QgsProcessingException,
                       QgsFeature,
                       QgsGeometry,
                       QgsField,
                       QgsFields,
                       QgsWkbTypes,
                       QgsPointXY,
                       NULL)
from qgis.PyQt.QtCore import (QVariant)

#import matplotlib.pyplot as plt
import re


@alg(name='demstat', label="Calculate relative stats of summits in a DEM",
     group='sota', group_label="SOTA")
@alg.input(type=alg.SOURCE, name='INPUT', label='Summit layer',
           types=[QgsProcessing.TypeVectorLine])
@alg.input(type=alg.RASTER_LAYER, name='DEM', label='DEM layer')
@alg.input(type=alg.SINK, name='OUTPUT', label='Output layer')
def demstat(instance, parameters, context, feedback, inputs):
    """
    This algorithm will evaluate summits from the input layer for
    which definite elevation and col elevation information exists
    and compares to the values from the DEM
    """

    source = instance.parameterAsSource(parameters, 'INPUT', context)
    layer = instance.parameterAsRasterLayer(parameters, 'DEM', context)

    # try to guess DEM source
    m = re.search('SRTM|ASTER|ALOS|TDX|GLO30', layer.name(), re.I)
    if not m:
        raise QgsProcessingException(
            f"Could not infer DEM source from layer name {layer.name()}")
    dem_name = m.group(0).upper()
    dem = layer.dataProvider()

    # output layer fields depend on available DEM layers
    fields = QgsFields()
    fields.append(QgsField("ID", QVariant.String))
    fields.append(QgsField("Elevation", QVariant.Int))
    fields.append(QgsField("Col Elevation", QVariant.Int))
    fields.append(QgsField("Prominence", QVariant.Int))
    fields.append(QgsField("DEM ele", QVariant.Int))
    fields.append(QgsField("DEM col", QVariant.Int))
    fields.append(QgsField('DEM prom', QVariant.Int))
    fields.append(QgsField('Detected ele', QVariant.Int))
    fields.append(QgsField('Detected col', QVariant.Int))
    fields.append(QgsField('Detected prom', QVariant.Int))
    fields.append(QgsField('Pos error', QVariant.Double))
    fields.append(QgsField('Col error', QVariant.Double))
    fields.append(QgsField('Crossmatch', QVariant.String))
    fields.append(QgsField('Crosscorrect ele', QVariant.Int))
    fields.append(QgsField('Crosscorrect col', QVariant.Int))
    fields.append(QgsField('Crosscorrect prom', QVariant.Int))
    
    (sink, dest_id) = instance.parameterAsSink(
        parameters, 'OUTPUT', context, fields, QgsWkbTypes.LineString,
        source.sourceCrs())

    if sink is None:
        raise QgsProcessingException(
            instance.invalidSinkError(parameters, 'OUTPUT'))

    # ele = []
    # err = []

    # cycle through the features in two stes
    # first get the position info for later cross-checking
    summits = {}
    for f in source.getFeatures():
        gp = f.geometry().constParts()
        
        next(gp)
        for d in ['SRTM', 'ASTER', 'ALOS', 'TDX', 'GLO30']:
            if f[f'{d} Elevation'] != NULL:
                g = next(gp)
            if d == dem_name:
                break
        
        v = g.vertices()
        pos = QgsPointXY(next(v))
        for c in v:
            pass
        
        col = QgsPointXY(c)
        summits[f['ID']] = [pos, col, f[f'{dem_name} Elevation'],
                                      f[f'{dem_name} Col elevation']]

    for f in source.getFeatures():
        # ignore summits that do not have elevation or col elevation specified
        if f['Elevation'] == NULL or f['Col elevation'] == NULL:
            continue

        # also ignore summits that are due to be further checked
        if f['Notes'] == 'check':
            continue

        # sample the DEM layer
        g = f.geometry()
        pos = QgsPointXY(g.vertexAt(0))
        col = QgsPointXY(g.vertexAt(1))
        dp, dpok = dem.sample(pos, 1)
        dc, dcok = dem.sample(col, 1)

        # if sampling fails, also ignore the summit
        if not dpok or not dcok:
            continue

        feature = QgsFeature(fields)
        feature['ID'] = f['ID']
        feature['Elevation'] = f['Elevation']
        feature['Col Elevation'] = f['Col Elevation']
        feature['Prominence'] = f['Elevation'] - f['Col Elevation']

        feature['DEM ele'] = dp
        feature['DEM col'] = dc
        feature['DEM prom'] = dp - dc

        if f[f'{dem_name} Elevation'] != NULL:
            feature['Detected ele'] = f[f'{dem_name} Elevation']
            feature['Detected col'] = f[f'{dem_name} Col elevation']
            feature['Detected prom'] = feature['Detected ele'] - feature['Detected col']

            feature['Pos error'] = pos.distance(summits[f['ID']][0])
            feature['Col error'] = col.distance(summits[f['ID']][1])

            # try to detect any crossmatches
            # search the feature Cross property and if any position or col
            # is closer than the actual position, take it as the preferred
            # crosscorrect value
            if f['Cross'] != NULL:
                errp = feature['Pos error']
                errc = feature['Col error']
                crossp = None
                crossc = None
                for s in f['Cross'].split():
                    p = pos.distance(summits[s][0])
                    if p < errp:
                        errp = p
                        crossp = s
                    c = col.distance(summits[s][1])
                    if c < errc:
                        errc = c
                        crossc = s
                
                p = feature['Detected ele']
                c = feature['Detected col']
                if crossp or crossc:
                    feature['Crossmatch'] = ' '.join(x for x in (crossp, crossc) if x)
                if crossp:
                    feature['Crosscorrect ele'] = summits[crossp][2]
                    p = summits[crossp][2]
                if crossc:
                    feature['Crosscorrect col'] = summits[crossc][3]
                    c = summits[crossc][3]
                    
                if crossp or crossc:
                    feature['Crosscorrect prom'] = p - c
                

        geometry = QgsGeometry.fromPolylineXY([pos, col])
        feature.setGeometry(geometry)

        sink.addFeature(feature)

        # ele.append(feature['Elevation'])
        # err.append(feature['Detected prom'] - feature['Prominence'])

    # plt.scatter(ele, err)
    # plt.show()