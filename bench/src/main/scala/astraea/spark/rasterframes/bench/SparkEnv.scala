/*
 * This software is licensed under the Apache 2 license, quoted below.
 *
 * Copyright 2017 Astraea, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may not
 * use this file except in compliance with the License. You may obtain a copy of
 * the License at
 *
 *     [http://www.apache.org/licenses/LICENSE-2.0]
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations under
 * the License.
 *
 */

package astraea.spark.rasterframes.bench

import astraea.spark.rasterframes._
import org.apache.spark.sql.SparkSession
import org.openjdk.jmh.annotations.{Level, TearDown}

/**
 *
 * @author sfitch 
 * @since 10/5/17
 */
trait SparkEnv {
  @transient
  val spark = SparkSession.builder
//    .master("local-cluster[2, 2, 1024]")
//    .config("spark.driver.extraClassPath", sys.props("java.class.path"))
//    .config("spark.executor.extraClassPath", sys.props("java.class.path"))
//    .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
    .master("local[*]")
    .appName(getClass.getSimpleName)
    .config("spark.ui.enabled", false)
    .config("spark.ui.showConsoleProgress", false)
    .getOrCreate
    .withRasterFrames

  spark.sparkContext.setLogLevel("ERROR")

  @TearDown(Level.Trial)
  def shutdown(): Unit =  spark.stop()
}
