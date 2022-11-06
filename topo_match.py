# -*- coding: utf-8 -*-

"""
QGIS Processing algorithm merging the topo25 layer data with Landserf layer
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


@alg(name='topomatch', label="Match topo25 layer with merged summit layer",
     group='sota', group_label="SOTA")
@alg.input(type=alg.SOURCE, name='INPUT', label='Summit layer',
           types=[QgsProcessing.TypeVectorLine])
@alg.input(type=alg.SOURCE, name='REF', label='Reference layer',
           types=[QgsProcessing.TypeVectorLine])
@alg.input(type=alg.SINK, name='OUTPUT', label='Output layer')
@alg.input(type=alg.SINK, name='REM', label='Remaining reference')
def topo25match(instance, parameters, context, feedback, inputs):
    """
    This algorithm will parse through the input and reference layers and
    tries to match them
    Matched features will output into the output layer merging in
    elevation and col elevation data, as well as notes
    Non-matching features will be stored in the remaining layer to be
    manually evaluated
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

    fields = reference.fields()
    fields.append(QgsField("Match", QVariant.String))
    (remainder, rem_id) = instance.parameterAsSink(
        parameters, 'OUTPUT', context,
        fields, reference.wkbType(), reference.sourceCrs())

    # create spatial index of the reference summit and col positions
    summits = QgsSpatialIndex()
    cols = QgsSpatialIndex()
    index = 0
    ref_list = []
    for f in reference.getFeatures():
        if not f.hasGeometry():
            continue

        # ignore summits marked for delete
        if f['action'] == 'delete':
            continue

        g = f.geometry()
        gs = QgsGeometry(g.vertexAt(0))
        fp = QgsFeature()
        fp.setGeometry(gs)
        fp.setId(index)
        summits.addFeature(fp)
        gc = QgsGeometry(g.vertexAt(g.constGet().nCoordinates() - 1))
        fp = QgsFeature()
        fp.setGeometry(gc)
        fp.setId(index)
        cols.addFeature(fp)
        ref_list.append(f)
        index += 1

    matched = set()
    candidate = {}
    # and now go through the source layer and update the fields
    for f in source.getFeatures():
        if feedback.isCanceled():
            break

        g = f.geometry()
        # try to find nearest reference summit
        i = summits.nearestNeighbor(QgsGeometry(g.vertexAt(0)), 1, 0.005)
        if i:
            i = i[0]
            j = cols.nearestNeighbor(QgsGeometry(g.vertexAt(1)), 1, 0.01)
            if i in j:
                # found the match
                rf = ref_list[i]
                # switchable summits will not be refed over
                if 'switch' in rf['action']:
                    notes = []
                else:
                    matched.add(i)
                    f['Reference'] = rf['ref']
                    notes = [] if rf['action'] == 'ok' else [rf['action']]
                if not f['Name']:
                    f['Name'] = rf['name']
                if not f['Elevation']:
                    if rf['check ele']:
                        if rf['check ele'].isdecimal():
                            f['Elevation'] = int(rf['check ele'])
                            g.moveVertex(rf.geometry().vertexAt(0), 0)
                            f.setGeometry(g)
                        else:
                            notes.append(f"ele:{rf['check ele']}")
                if not f['Col elevation']:
                    if rf['check col']:
                        if rf['check col'].isdecimal():
                            f['Col elevation'] = int(rf['check col'])
                            g.moveVertex(rf.geometry().vertexAt(1), 1)
                            f.setGeometry(g)
                        else:
                            notes.append(f"col:{rf['check col']}")
            else:
                candidate[i] = f['ID']
                
            if f['Elevation'] and f['Col elevation']:
                f['Prominence'] = f['Elevation'] - f['Col elevation']
            if notes:
                f['Notes'] = '; '.join(notes)

        sink.addFeature(f, QgsFeatureSink.FastInsert)

    # finally build the remaining list
    for i, f in enumerate(ref_list):
        f.padAttributes(1)
        if i not in matched:
            if i in candidate:
                f.setAttribute(f.attributeCount() - 1, candidate[i])
            remainder.addFeature(f, QgsFeatureSink.FastInsert)

    return {'OUTPUT': dest_id, 'REM': rem_id}
