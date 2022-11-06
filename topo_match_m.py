# -*- coding: utf-8 -*-

"""
QGIS Processing algorithm matching the manually updated remainder of the topo25
layer data with Landserf layer
"""
__author__ = "dr. Kertész Csaba Zoltán"
__email__ = "csaba.kertesz@unitbv.ro"
__copyright__ = "Copyright 2022, dr. Kertész Csaba-Zoltán"
__license__ = "MIT"


from qgis.processing import alg
from qgis.core import (QgsProcessing,
                       QgsProcessingException,
                       QgsFeature,
                       QgsFeatureSink,
                       QgsGeometry,
                       QgsField,
                       QgsSpatialIndex)
from qgis.PyQt.QtCore import (QVariant)


@alg(name='topomatchm', label="Match remainder topo25 layer with merged summit layer",
     group='sota', group_label="SOTA")
@alg.input(type=alg.SOURCE, name='INPUT', label='Summit layer',
           types=[QgsProcessing.TypeVectorLine])
@alg.input(type=alg.SOURCE, name='REF', label='Reference layer',
           types=[QgsProcessing.TypeVectorLine])
@alg.input(type=alg.SINK, name='OUTPUT', label='Output layer')
def topo25match(instance, parameters, context, feedback, inputs):
    """
    This algorithm will parse through the input and reference layers and
    tries to match them based on the manually inserted Match field
    of the reference layer.
    Matched features will output into the output layer merging in
    elevation and col elevation data, as well as notes
    """

    source = instance.parameterAsSource(parameters, 'INPUT', context)
    reference = instance.parameterAsSource(parameters, 'REF', context)

    if source is None or reference is None:
        raise QgsProcessingException(
            instance.invalidSourceError(
                parameters, 'INPUT' if source is None else 'REF'))

    (sink, dest_id) = instance.parameterAsSink(
        parameters, 'OUTPUT', context,
        source.fields(), source.wkbType(), source.sourceCrs())

    # create dict with the reference data for easier finding
    refs = dict((r['Match'], r) for r in reference.getFeatures() if r['Match'])

    features = []
    # and now go through the source layer and update the fields
    for f in source.getFeatures():
        if feedback.isCanceled():
            break

        if f['ID'] in refs:
            rf = refs[f['ID']]
            g = f.geometry()

            # if summit is marked as move, do not copy over the referen ce
            if 'move' in rf['action']:
                notes = []
            else:
                f['Reference'] = rf['ref']
                notes = [] if rf['action'] in ('ok', 'move') else [rf['action']]
            if not f['Name']:
                f['Name'] = rf['name']
            if not f['Elevation']:
                if rf['check ele']:
                    if rf['check ele'].isdecimal():
                        f['Elevation'] = int(rf['check ele'])
                    else:
                        notes.append(f"ele:{rf['check ele']}")
                    g.moveVertex(rf.geometry().vertexAt(0), 0)
                    f.setGeometry(g)

            if not f['Col elevation']:
                if rf['check col']:
                    if rf['check col'].isdecimal():
                        f['Col elevation'] = int(rf['check col'])
                    else:
                        notes.append(f"col:{rf['check col']}")
                    g.moveVertex(rf.geometry().vertexAt(1), 1)
                    f.setGeometry(g)

            if notes:
                f['Notes'] = '; '.join(notes)

        if f['Elevation'] and f['Col elevation']:
            f['Prominence'] = f['Elevation'] - f['Col elevation']
    
        features.append(f)

    features.sort(key=lambda f: (0, f['Reference']) if f['Reference'] else
                                (1, -f['Prominence']))

    for i, f in enumerate(features):
        f['fid'] = i

    sink.addFeatures(features, QgsFeatureSink.FastInsert)

    return {'OUTPUT': dest_id}
