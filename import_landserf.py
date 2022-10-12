# -*- coding: utf-8 -*-

"""
QGIS Processing algorithm for importing Landserf summits
"""
__author__ = "dr. Kertész Csaba Zoltán"
__email__ = "csaba.kertesz@unitbv.ro"
__copyright__ = "Copyright 2022, dr. Kertész Csaba-Zoltán"
__license__ = "MIT"

from qgis.PyQt.QtCore import (QCoreApplication,
                              QVariant)
from qgis.core import (QgsField,
                       QgsFields,
                       QgsFeature,
                       QgsProcessing,
                       QgsProcessingUtils,
                       QgsFeatureSink,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterGeometry,
                       QgsWkbTypes,
                       QgsCoordinateReferenceSystem,
                       QgsPoint,
                       QgsPointXY,
                       QgsGeometry)
from qgis import processing
import re

# precompiled regex
re_summit = re.compile(r'P ([+-]?(?:\d+\.|\.\d)\d*) ([+-]?(?:\d+\.|\.\d)\d*) ([+-]?(?:\d+\.|\.?\d)\d*)')
re_ridge = re.compile(r'L (\d+) ([+-]?(?:\d+\.|\.\d)\d*)')
re_coord = re.compile(r' ([+-]?(?:\d+\.|\.\d)\d*) ([+-]?(?:\d+\.|\.\d)\d*)')

class ImportLandserf(QgsProcessingAlgorithm):
    """
    This is a Processing tool for importing Landserf vector text format
    (.lst) file and convert it to a LineString vector layer with one entry
    for each summit detected, a line from the summit to the col along
    the main ridge
    
    It needs the Landserf output file and a raster layer with the DEM data
    used by Landserf to identify actual elevation values
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    FILE = 'FILE'
    DEM = 'DEM'
    OUTLINE = 'OUTLINE'
    OUTPUT = 'OUTPUT'

    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return ImportLandserf()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'importlandserf'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('Import Landserf summits')

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
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it..
        """
        return self.tr("Import Landserf generated summit list into a vector layer")

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        # the lst file
        self.addParameter(
            QgsProcessingParameterFile(
                self.FILE,
                self.tr('Input file'),
                extension = 'lst'
            )
        )

        # DEM layer.
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.DEM,
                self.tr('DEM layer')
            )
        )
        
        # outline
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.OUTLINE,
                self.tr('Clipping area'),
                optional = True,
                types = [QgsWkbTypes.MultiPolygon]
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

        # check Landserf file
        file = self.parameterAsFile(parameters, self.FILE, context)
        summits = []
        pos = None
        col = None
        ridge = None
        elems = 0
        lineno = 0
        with open(file, "r") as f:
            for line in f:
                lineno += 1
                line = line.rstrip()
                if not line:
                    continue
                if pos is None:
                    m = re_summit.fullmatch(line)
                    if not m:
                        raise QgsProcessingException(
                            f"Wrong summit entry in Landserf vector file line {lineno}: '{line}'"
                        )
                    pos = (float(m.group(1)), float(m.group(2)), int(float(m.group(3))))
                elif col is None:
                    m = re_summit.fullmatch(line)
                    if not m:
                        raise QgsProcessingException(
                            f"Wrong col entry in Landserf vector file line {lineno}: '{line}'"
                        )
                    col = (float(m.group(1)), float(m.group(2)), int(float(m.group(3))))
                elif ridge is None:
                    m = re_ridge.fullmatch(line)
                    if not m:
                        raise QgsProcessingException(
                            f"Wrong ridge entry in Landserf vector file line {lineno}: '{line}'"
                        )
                    elems = int(m.group(1))
                    ridge = []
                elif elems > 0:
                    m = re_coord.fullmatch(line)
                    if not m:
                        raise QgsProcessingException(
                            f"Wrong coordinate entry in Landserf vector file line {lineno}: '{line}'"
                        )
                    ridge.insert(0, (float(m.group(1)), float(m.group(2))))
                    elems -= 1
                    if elems == 0:
                        # at last ridge element make some more sanity checks
                        if pos[0:2] != ridge[0] or col[0:2] != ridge[-1]:
                            raise QgsProcessingException(
                                f"Summit/col position doesn't match ridge start/end in Lanserf vector file line {lineno}"
                            )
                        if pos[2] != -col[2]:
                            raise QgsProcessingException(
                                f"Summit/col prominence value mismatch {pos[2]} <> {col[2]}"
                            )
                        # if values seem ok, add ridge to summit list
                        # and reset values for next round
                        summits.append({'prom': pos[2], 'ridge': ridge})
                        pos = None
                        col = None
                        ridge = None
                else:
                    raise QgsProcessingException(
                        f"Unrecognized/out of order line in Landserf vector file line {lineno}: {line}"
                    )
            # check if loop ends without storing last value
            if col or pos or ridge:
                raise QgsProcessingException(
                    f"Unterminated summit data in Landserf vector file"
                )
        if not summits:
            raise QgsProcessingException(f"No summits read from {file}")
        
        # Retrieve the source DEM
        dem_layer = self.parameterAsRasterLayer(parameters, self.DEM, context)
        if dem_layer is None:
            raise QgsProcessingException(self.invalidRasterError(parameters, self.DEM))
        dem = dem_layer.dataProvider()
        demstats = dem.bandStatistics(1)
        
        # outline
        outline = self.parameterAsSource(parameters, self.OUTLINE, context)
        if outline:
            g = [f.geometry() for f in outline.getFeatures() if f.hasGeometry()]
            if len(g) > 1:
                gg = QgsGeometry.unaryUnion(g)
            elif len(g) == 1:
                gg = g[0]
            if gg.isEmpty():
                raise QgsProcessingException( f"Couldn't create combined outline geometry: {gg.lastError()}")
            clipEngine = QgsGeometry.createGeometryEngine(gg.constGet())
            clipEngine.prepareGeometry()
        else:
            clipEngine = None
       
        # retrieve the output layer. The 'dest_id' variable is used
        # to uniquely identify the feature sink, and must be included in the
        # dictionary returned by the processAlgorithm function.
        # output should be LineString vector layer WGS84 with the following
        # fields:
        fields = QgsFields()
        fields.append(QgsField("ID", QVariant.Int))
        fields.append(QgsField("Name", QVariant.String))
        fields.append(QgsField("Elevation", QVariant.Int))
        fields.append(QgsField("Col elevation", QVariant.Int))
        fields.append(QgsField("Notes", QVariant.String))
        #fields.appendExpressionField(QgsField("Prominence", QVariant.Int), 2)
        
        (sink, self.dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            QgsWkbTypes.LineString,
            QgsCoordinateReferenceSystem("EPSG:4326")
        )

        # If sink was not created, throw an exception to indicate that the algorithm
        # encountered a fatal error. The exception text can be any string, but in this
        # case we use the pre-built invalidSinkError method to return a standard
        # helper text for when a sink cannot be evaluated
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        # Send some information to the user
        feedback.pushInfo(f"Loaded {len(summits)} summit points. Filtering and adding to output layer")


        # Compute the number of steps to display within the progress bar and
        # get features from source
        total = 100.0 / len(summits)

        fid = 0
        for current, summit in enumerate(summits):
            # Stop the algorithm if cancel button has been clicked
            if feedback.isCanceled():
                break

            # get ridgeline
            poly = [QgsPointXY(x[0], x[1]) for x in summit['ridge']]

            # check against clipping outline
            if clipEngine and not clipEngine.contains(QgsPoint(poly[0])):
                continue

            ele, sok = dem.sample(poly[0], 1)
            cele, cok = dem.sample(poly[-1], 1)
            
            # if failed to sample or sampled value is the minimum value of
            # the raster layer then ignore the summit
            if not sok or not cok:
                continue
            if cele == demstats.minimumValue:
                continue
                
            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromPolylineXY(poly))
            attribs = [fid, str(summit['prom']), ele, cele, None]
            feature.setAttributes(attribs)
            
            # Add a feature in the sink
            sink.addFeature(feature, QgsFeatureSink.FastInsert)
            fid += 1

            # Update the progress bar
            feedback.setProgress(int(current * total))

        # Return the results of the algorithm. In this case our only result is
        # the feature sink which contains the processed features, but some
        # algorithms may return multiple feature sinks, calculated numeric
        # statistics, etc. These should all be included in the returned
        # dictionary, with keys matching the feature corresponding parameter
        # or output names.
        return {self.OUTPUT: self.dest_id}
        
    def postProcessAlgorithm(self, context, feedback):
        # do some layer fiddling with the output sink
        layer = QgsProcessingUtils.mapLayerFromString(self.dest_id, context)
        layer.addExpressionField('"Elevation" - "Col elevation"', QgsField("Prominence", QVariant.Int))

        return {self.OUTPUT: self.dest_id}
