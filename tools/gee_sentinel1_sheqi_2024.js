// Google Earth Engine companion script for Sentinel-1 SAR plot flood metrics.
// Run in https://code.earthengine.google.com/ after uploading field polygons
// as an EE FeatureCollection (with property `field_id`), or using the sample
// plain grids below. Exported CSV matches `data_integration.sar_metrics_template()`.

var SHEQI_SAMPLES = ee.FeatureCollection([
  ee.Feature(ee.Geometry.Rectangle([112.89, 32.85, 112.92, 32.88]), {field_id: 'SHEQI_PLAIN_01'}),
  ee.Feature(ee.Geometry.Rectangle([112.91, 32.85, 112.94, 32.88]), {field_id: 'SHEQI_PLAIN_02'}),
  ee.Feature(ee.Geometry.Rectangle([112.89, 32.88, 112.92, 32.91]), {field_id: 'SHEQI_PLAIN_03'}),
  ee.Feature(ee.Geometry.Rectangle([113.02, 33.10, 113.05, 33.13]), {field_id: 'SHEQI_CTRL_01'})
]);

var EVENT_ID = 'FLOOD-2024-07-SHEQI';
var METHOD_VERSION = 'gee_s1_vv_lt_minus14_and_delta_le_minus2p5_v0.1';

// 1. Pre-flood baseline median (2024-06-01 to 2024-07-10)
var s1Base = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(SHEQI_SAMPLES)
  .filterDate('2024-06-01', '2024-07-10')
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.eq('orbitProperties_pass', 'ASCENDING'))
  .select('VV')
  .median()
  .rename('VV_pre');

// 2. Event-window Sentinel-1 scenes (2024-07-11 to 2024-08-25)
var s1Events = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(SHEQI_SAMPLES)
  .filterDate('2024-07-11', '2024-08-25')
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.eq('orbitProperties_pass', 'ASCENDING'))
  .select('VV');

var rows = s1Events.map(function(img) {
  var dateStr = ee.Date(img.get('system:time_start')).format('YYYY-MM-dd');
  var sceneId = img.get('system:index');
  var deltaVv = img.subtract(s1Base).rename('delta_vv');
  var floodedMask = img.lt(-14.0).and(deltaVv.lte(-2.5)).or(img.lt(-16.5)).rename('flooded');

  return floodedMask.multiply(100).reduceRegions({
    collection: SHEQI_SAMPLES,
    reducer: ee.Reducer.mean(),
    scale: 10
  }).map(function(feat) {
    return feat.set({
      event_id: EVENT_ID,
      event_date: dateStr,
      flood_start_date: '2024-07-14',
      flood_end_date: '2024-07-28',
      recession_date: '2024-07-28',
      flooded_area_pct: feat.get('mean'),
      max_water_depth_m: '',
      source_scene_ids: sceneId,
      method_version: METHOD_VERSION
    });
  });
}).flatten();

Export.table.toDrive({
  collection: rows,
  description: 'sheqi_2024_sar_flood_metrics',
  fileFormat: 'CSV',
  selectors: [
    'field_id',
    'event_id',
    'event_date',
    'flood_start_date',
    'flood_end_date',
    'recession_date',
    'flooded_area_pct',
    'max_water_depth_m',
    'source_scene_ids',
    'method_version'
  ]
});
