// scripts/generateIconsMap.js
import fs from "fs";
import path from "path";
import * as lucideIcons from "lucide-react";

const outputPath = path.resolve("./src/assets/iconsMap.js");

// Генерация кода для iconsMap
function generateIconsMap(icons) {
  let imports = `import {\n`;
  let mappings = "const iconsMap = {\n";

  Object.keys(icons).forEach((iconName, idx, arr) => {
    imports += `  ${iconName}${idx < arr.length - 1 ? "," : ""}\n`;
    mappings += `  "${iconName}": ${iconName},\n`;
  });

  imports += `} from "lucide-react";\n\n`;
  mappings += "};\n\nexport default iconsMap;\n";

  return imports + mappings;
}

const fileContent = generateIconsMap(lucideIcons);
fs.writeFileSync(outputPath, fileContent);

console.log(`✅ iconsMap.js создан: ${outputPath}`);
