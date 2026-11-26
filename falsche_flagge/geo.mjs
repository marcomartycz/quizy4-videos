import fs from 'fs'; import * as topo from 'topojson-client';
const t = JSON.parse(fs.readFileSync('node_modules/world-atlas/countries-50m.json'));
const fc = topo.feature(t, t.objects.countries);
fs.writeFileSync('countries.geojson', JSON.stringify(fc));
console.log(fc.features.length, fc.features.filter(f=>/Spain|Italy|Germany|France|Sweden|Norway|Finland|Denmark|Portugal|Greece|Austria|Hungary/.test(f.properties.name)).map(f=>f.properties.name).join(','));
