const babelParser = require("@babel/parser");
const fs = require("fs");
const code = fs.readFileSync(0, "utf-8");

try {
  const ast = babelParser.parse(code, {
    sourceType: "module",
    plugins: ["jsx", "typescript", "decorators-legacy"] 
  });
  console.log(JSON.stringify(ast));
} catch (error) {
  console.error(JSON.stringify({ error: error.message }));
  process.exit(1);
}
