# -*- coding: utf-8 -*-

"""
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from qgis.PyQt.QtCore import (QCoreApplication,
                              QVariant)
from qgis.core import (QgsProcessing,
                       QgsGeometry,
                       QgsPointXY,
                       QgsFeature,
                       QgsField,
                       QgsFields,
                       QgsWkbTypes,
                       QgsSpatialIndex,
                       QgsFeatureSink,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterMultipleLayers,
                       QgsProcessingParameterCrs,
                       QgsProcessingParameterDistance,
                       QgsProcessingParameterFeatureSink)
import re
import sys


class MergeSummitLayers(QgsProcessingAlgorithm):
    """
    This is a helper Processing algorithm, to merge the existing
    summit layers imported from Landserf into a combination where related
    summits are grouped into a single MultiLineString geometry
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    LAYERS = 'LAYERS'
    CRS = 'CRS'
    DISTANCE = 'DISTANCE'
    OUTPUT = 'OUTPUT'

    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return MergeSummitLayers()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'mergesummitlayers'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('Merge Summit Layers')

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr('SOTA')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'sota'

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and
        the parameters and outputs associated with it..
        """
        return self.tr(
            "Merging solution form summits extracted from different DEMs")
            
    def flags(self):
        return super().flags() | QgsProcessingAlgorithm.FlagNoThreading
            
    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        # We add the input vector features source. It can have any kind of
        # geometry.
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.LAYERS,
                self.tr('Input layers'),
                QgsProcessing.TypeVectorLine
            )
        )

        # layer come from different CRS maybe a good idea to select one for
        # destination, it's optional though, if no CRS is specified it will
        # be chosen from the first input layer
        self.addParameter(
            QgsProcessingParameterCrs(
                self.CRS,
                self.tr('Destination CRS'),
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterDistance(
                self.DISTANCE,
                self.tr('Neighbour distance for matching'),
                parentParameterName=self.CRS,
                minValue=0.0
            )
        )

        # We add a feature sink in which to store our processed features (this
        # usually takes the form of a newly created vector layer when the
        # algorithm is run in QGIS).
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Output layer')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """

        # input layers
        layers = self.parameterAsLayerList(
            parameters,
            self.LAYERS,
            context
        )

        if layers is None:
            raise QgsProcessingException(
                self.invalidSourceError(parameters, self.INPUT))

        # output CRS
        outputCrs = self.parameterAsCrs(parameters, self.CRS, context)

        # neighbourhood threshold
        distance = self.parameterAsDouble(parameters, self.DISTANCE, context)

        totalFeatureCount = 0
        fields = QgsFields()
        fields.append(QgsField("fid", QVariant.LongLong))
        fields.append(QgsField("ID", QVariant.String))
        fields.append(QgsField("Name", QVariant.String))
        fields.append(QgsField("Elevation", QVariant.Int))
        fields.append(QgsField("Col elevation", QVariant.Int))
        fields.append(QgsField("Reference", QVariant.String))
        fields.append(QgsField("Prominence", QVariant.Int))
        fields.append(QgsField("Merge", QVariant.String))
        fields.append(QgsField("Cross", QVariant.String))
        fields.append(QgsField("Notes", QVariant.String))

        # create an ordered layer list, to make sure that geometry parts will
        # always be in a known order
        # TODO: somehow move ordering into parameter dialog
        layerList = {
            'SRTM': None,
            'ASTER': None,
            'ALOS': None,
            'TDX': None,
            'GLO30': None
        }

        # go through layers first to determine output parameters
        for layer in layers:
            if feedback.isCanceled():
                break

            if not outputCrs.isValid() and layer.crs().isValid():
                outputCrs = layer.crs()
                feedback.pushInfo(
                    self.tr(f"Using destination CRS {outputCrs.authid()}"))

            totalFeatureCount += layer.featureCount()
            m = re.search('|'.join(layerList.keys()), layer.name(), re.I)
            if not m:
                raise QgsProcessingException(
                    f"Layer name {layer.name()} does not infer a known DEM type")
            if layerList[m.group(0).upper()]:
                raise QgsProcessingException(
                    f"Layer {layer.name()} appears to be the same DEM as {layerList[m.group(0)].name()}")
            layerList[m.group(0).upper()] = layer

        for dem in layerList:
            if layerList[dem]:
                fields.append(QgsField(f"{dem} Elevation", QVariant.Int))
                fields.append(QgsField(f"{dem} Col elevation", QVariant.Int))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            QgsWkbTypes.MultiLineString,
            outputCrs
        )

        if sink is None:
            raise QgsProcessingException(
                self.invalidSinkError(parameters, self.OUTPUT))

        # Send some information to the user
        feedback.pushInfo(f"CRS is {outputCrs.authid()}")

        # Compute the number of steps to display within the progress bar and
        # get features from source
        total = 100.0 / totalFeatureCount if totalFeatureCount else 0
        current = 0

        summits = []
        current = 0
        sisummit = QgsSpatialIndex()
        sicol = QgsSpatialIndex()

        for dem, layer in layerList.items():
            # stop algorithm if cancel button was pressed
            if feedback.isCanceled():
                break

            if not layer:
                continue
                
            feedback.pushInfo(f"DEM {dem}")
            for f in layer.getFeatures():
                if not f.hasGeometry():
                    continue

                g = f.geometry()
                gs = QgsGeometry(g.vertexAt(0))
                fp = QgsFeature()
                fp.setGeometry(gs)
                fp.setId(current)
                sisummit.addFeature(fp)
                gc = QgsGeometry(g.vertexAt(g.constGet().nCoordinates() - 1))
                fp = QgsFeature()
                fp.setGeometry(gc)
                fp.setId(current)
                sicol.addFeature(fp)
                summits.append(
                    (dem, f['Elevation'], f['Col elevation'], g, gs, gc))
                current += 1

        # make neighborhood list in the spatial indexes
        smatch = []
        cmatch = []
        dmatch = {}
        for i in range(len(summits)):
            s = sisummit.nearestNeighbor(summits[i][4], 5, distance)
            c = sicol.nearestNeighbor(summits[i][5], 20, distance)
            m = set(x for x in s if x in c)
            smatch.append([x for x in s if x not in c])
            cmatch.append([x for x in c if x not in s])
            m |= set(item for x in m if x in dmatch for item in dmatch[x])
            for x in m:
                dmatch[x] = tuple(sorted(m))
        dm = set(dmatch.values())

        def meanXY(points):
            return QgsPointXY(sum(p.asPoint().x() for p in points) / len(points),
                              sum(p.asPoint().y() for p in points) / len(points))

        features = []
        fmap = {}
        for m in dm:
            gm = QgsGeometry.fromPolylineXY([meanXY([summits[i][4] for i in m]),
                                             meanXY([summits[i][5] for i in m])])
            f = QgsFeature(fields)
            f.setGeometry(QgsGeometry.collectGeometry(
                [gm] + [summits[i][3] for i in m]))
            e = 0
            c = 0
            ss = []
            cc = []
            for i in m:
                f[f'{summits[i][0]} Elevation'] = summits[i][1]
                f[f'{summits[i][0]} Col elevation'] = summits[i][2]
                e += summits[i][1]
                c += summits[i][2]
                fmap[i] = len(features)
                ss.extend(smatch[i])
                cc.extend(cmatch[i])
            f['Prominence'] = (e - c) / len(m)
            if ss:
                f['Merge'] = ','.join(f'{x}' for x in ss)
            if cc:
                f['Cross'] = ','.join(f'{x}' for x in cc)

            features.append(f)

        index, features = zip(*sorted(enumerate(features), key=lambda s: s[1]['Prominence'], reverse=True))
        index = [x[0] for x in sorted(enumerate(index), key=lambda s: s[1])]
        #index = sorted(range(len(features)), key=lambda s: features[s]['Prominence'], reverse=True)
        for i, f in enumerate(features):
            f['fid'] = i
            f['ID'] = f'S{i+1:04}'
            if f['Merge']:
                m = set(fmap[int(x)] for x in f['Merge'].split(','))
                f['Merge'] = ' '.join(f'S{index[x]+1:04}' for x in m)
            if f['Cross']:
                m = set(fmap[int(x)] for x in f['Cross'].split(','))
                f['Cross'] = ' '.join(f'S{index[x]+1:04}' for x in m)

        sink.addFeatures(features, QgsFeatureSink.FastInsert)

        # Return the results of the algorithm. In this case our only result is
        # the feature sink which contains the processed features, but some
        # algorithms may return multiple feature sinks, calculated numeric
        # statistics, etc. These should all be included in the returned
        # dictionary, with keys matching the feature corresponding parameter
        # or output names.
        return {self.OUTPUT: dest_id}
