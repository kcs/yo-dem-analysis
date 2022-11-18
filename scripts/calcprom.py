# -*- coding: utf-8 -*-

"""
QGIS Processing algorithm identify prominence from each DEM
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


@alg(name='calcprom', label="Calculate prominences of each DEM",
     group='sota', group_label="SOTA")
@alg.input(type=alg.SOURCE, name='INPUT', label='Summit layer',
           types=[QgsProcessing.TypeVectorLine])
@alg.input(type=alg.RASTER_LAYER, name='SRTM', label='SRTM DEM',
           optional=True)
@alg.input(type=alg.RASTER_LAYER, name='ASTER', label='ASTER DEM',
           optional=True)
@alg.input(type=alg.RASTER_LAYER, name='ALOS', label='ALOS DEM',
           optional=True)
@alg.input(type=alg.RASTER_LAYER, name='TDX', label='TanDEM-X DEM',
           optional=True)
@alg.input(type=alg.RASTER_LAYER, name='GLO30', label='GLO30 DEM',
           optional=True)
@alg.input(type=alg.SINK, name='OUTPUT', label='Output layer')
def calcprom(instance, parameters, context, feedback, inputs):
    """
    This algorithm will calculate the prominences of the summits
    stored in the Summit Layer from each of the DEM rasters given
    as optional inputs.
    The output will store the actual prominence and each
    calculated prominence for each of the summits which have a
    definite actual prominence (both Elevation and Col elevation
    are defined)
    """

    source = instance.parameterAsSource(parameters, 'INPUT', context)
    dems = {}

    for d in ['SRTM', 'ASTER', 'ALOS', 'TDX', 'GLO30']:
        layer = instance.parameterAsRasterLayer(parameters, d, context)
        if layer:
            dems[d] = layer

    if not dems:
        raise QgsProcessingException(
            "At least one DEM layer must be specified")

    # output layer fields depend on available DEM layers
    fields = QgsFields()
    fields.append(QgsField("ID", QVariant.String))
    fields.append(QgsField("Prominence", QVariant.Int))
    for d in dems:
        fields.append(QgsField(f"{d} Prominence", QVariant.Int))

    (sink, dest_id) = instance.parameterAsSink(
        parameters, 'OUTPUT', context, fields, QgsWkbTypes.LineString,
        source.sourceCrs())

    if sink is None:
        raise QgsProcessingException(
            instance.invalidSinkError(parameters, 'OUTPUT'))

    for f in source.getFeatures():
        # ignore summits that do not have elevation or col elevation specified
        if f['Elevation'] == NULL or f['Col elevation'] == NULL:
            continue

        feature = QgsFeature(fields)
        feature['ID'] = f['ID']
        feature['Prominence'] = f['Elevation'] - f['Col elevation']

        g = f.geometry()
        pos = QgsPointXY(g.vertexAt(0))
        col = QgsPointXY(g.vertexAt(1))

        for d in dems:
            dem = dems[d].dataProvider()
            dp, dpok = dem.sample(pos, 1)
            dc, dcok = dem.sample(col, 1)
            if dpok and dcok:
                feature[f"{d} Prominence"] = dp - dc

        geometry = QgsGeometry.fromPolylineXY([pos, col])
        feature.setGeometry(geometry)

        sink.addFeature(feature)
