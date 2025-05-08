const fs = require('node:fs');

fs.readFile('../input.txt', 'utf8', (err, data) => {
  if (err) {
    console.error(err);
    return;
  }
  data = data.trim();
  console.log(data.toUpperCase())
});
