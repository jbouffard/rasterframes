
from pyspark.sql import SparkSession, Column
from pyspark.sql.functions import *
from pyrasterframes import *
from pyrasterframes.rasterfunctions import *
from pathlib import Path
import os
import unittest

# version-conditional imports
import sys
if sys.version_info[0] > 2:
    import builtins
else:
    import __builtin__ as builtins


def _rounded_compare(val1, val2):
    print('Comparing {} and {} using round()'.format(val1, val2))
    return builtins.round(val1) == builtins.round(val2)


class RasterFunctionsTest(unittest.TestCase):


    @classmethod
    def setUpClass(cls):

        # gather Scala requirements
        jarpath = list(Path('../target').resolve().glob('pyrasterframes*.jar'))[0]
        os.environ["SPARK_CLASSPATH"] = jarpath.as_uri()

        # hard-coded relative path for resources
        cls.resource_dir = Path('./static').resolve()

        # spark session with RF
        cls.spark = SparkSession.builder.getOrCreate()
        cls.spark.sparkContext.setLogLevel('ERROR')
        print(cls.spark.version)
        cls.spark.withRasterFrames()

        # load something into a rasterframe
        rf = cls.spark.read.geotiff(cls.resource_dir.joinpath('L8-B8-Robinson-IL.tiff').as_uri()) \
            .withBounds() \
            .withCenter()

        # convert the tile cell type to provide for other operations
        cls.tileCol = 'tile'
        cls.rf = rf.withColumn('tile2', convertCellType(cls.tileCol, 'float32')) \
            .drop(cls.tileCol) \
            .withColumnRenamed('tile2', cls.tileCol).asRF()
        cls.rf.show()


    def test_identify_columns(self):
        cols = self.rf.tileColumns()
        self.assertEqual(len(cols), 1, '`tileColumns` did not find the proper number of columns.')
        print("Tile columns: ", cols)
        col = self.rf.spatialKeyColumn()
        self.assertIsInstance(col, Column, '`spatialKeyColumn` was not found')
        print("Spatial key column: ", col)
        col = self.rf.temporalKeyColumn()
        self.assertIsNone(col, '`temporalKeyColumn` should be `None`')
        print("Temporal key column: ", col)


    def test_tile_operations(self):
        df1 = self.rf.withColumnRenamed(self.tileCol, 't1').asRF()
        df2 = self.rf.withColumnRenamed(self.tileCol, 't2').asRF()
        df3 = df1.spatialJoin(df2).asRF()
        df3 = df3.withColumn('norm_diff', normalizedDifference('t1', 't2'))
        df3.printSchema()

        aggs = df3.agg(
            aggMean('norm_diff'),
        )
        aggs.show()
        row = aggs.first()

        self.assertTrue(_rounded_compare(row['agg_mean(norm_diff)'], 0))


    def test_general(self):
        meta = self.rf.tileLayerMetadata()
        self.assertIsNotNone(meta['bounds'])
        df = self.rf.withColumn('dims',  tileDimensions(self.tileCol)) \
            .withColumn('type', cellType(self.tileCol)) \
            .withColumn('dCells', dataCells(self.tileCol)) \
            .withColumn('ndCells', noDataCells(self.tileCol)) \
            .withColumn('min', tileMin(self.tileCol)) \
            .withColumn('max', tileMax(self.tileCol)) \
            .withColumn('mean', tileMean(self.tileCol)) \
            .withColumn('sum', tileSum(self.tileCol)) \
            .withColumn('stats', tileStats(self.tileCol)) \
            .withColumn('envelope', envelope('bounds')) \
            .withColumn('ascii', renderAscii(self.tileCol))

        df.show()

    def test_rasterize(self):
        # NB: This test just makes sure rasterize runs, not that the results are correct.
        withRaster = self.rf.withColumn('rasterize', rasterize('bounds', 'bounds', lit(42), 10, 10))
        withRaster.show()

    def test_reproject(self):
        reprojected = self.rf.withColumn('reprojected', reprojectGeometry('center', 'EPSG:4326', 'EPSG:3857'))
        reprojected.show()

    def test_aggregations(self):
        aggs = self.rf.agg(
            aggMean(self.tileCol),
            aggDataCells(self.tileCol),
            aggNoDataCells(self.tileCol),
            aggStats(self.tileCol),

            # Not currently working:
            # aggHistogram(self.tileCol),
        )
        aggs.show()
        row = aggs.first()

        self.assertTrue(_rounded_compare(row['agg_mean(tile)'], 10158))
        self.assertTrue(row['agg_data_cells(tile)'] == 250000)
        self.assertTrue(row['agg_nodata_cells(tile)'] == 0)
        self.assertTrue(row['aggStats(tile)'].dataCells == row['agg_data_cells(tile)'])


    def test_sql(self):

        self.rf.createOrReplaceTempView("rf")

        dims = self.rf.withColumn('dims',  tileDimensions(self.tileCol)).first().dims
        dims_str = """{}, {}""".format(dims.cols, dims.rows)

        self.spark.sql("""SELECT tile, rf_makeConstantTile(1, {}, 'uint16') AS One, 
                            rf_makeConstantTile(2, {}, 'uint16') AS Two FROM rf""".format(dims_str, dims_str)) \
            .createOrReplaceTempView("r3")

        ops = self.spark.sql("""SELECT tile, rf_localAdd(tile, One) AS AndOne, 
                                    rf_localSubtract(tile, One) AS LessOne, 
                                    rf_localMultiply(tile, Two) AS TimesTwo, 
                                    rf_localDivide(  tile, Two) AS OverTwo 
                                FROM r3""")

        ops.printSchema
        statsRow = ops.select(tileMean(self.tileCol).alias('base'),
                           tileMean("AndOne").alias('plus_one'),
                           tileMean("LessOne").alias('minus_one'),
                           tileMean("TimesTwo").alias('double'),
                           tileMean("OverTwo").alias('half')) \
                        .first()

        self.assertTrue(_rounded_compare(statsRow.base, statsRow.plus_one - 1))
        self.assertTrue(_rounded_compare(statsRow.base, statsRow.minus_one + 1))
        self.assertTrue(_rounded_compare(statsRow.base, statsRow.double / 2))
        self.assertTrue(_rounded_compare(statsRow.base, statsRow.half * 2))


def suite():
    functionTests = unittest.TestSuite()
    functionTests.addTest(RasterFunctionsTest('test_identify_columns'))
    functionTests.addTest(RasterFunctionsTest('test_general'))
    functionTests.addTest(RasterFunctionsTest('test_aggregations'))
    functionTests.addTest(RasterFunctionsTest('test_sql'))
    return functionTests


unittest.TextTestRunner().run(suite())



