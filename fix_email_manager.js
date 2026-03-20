const fs = require('fs');
const file = 'frontend/src/components/notifications/EmailSMSManager.jsx';
let content = fs.readFileSync(file, 'utf8');

// There are two identical buttons per item, one for view and one for edit.
// We already replaced both with 'Просмотр'. Let's fix the edit one.
// The structure is:
// <button className="p-2 text-gray-400 hover:text-blue-600" aria-label="Просмотр">
//   <Eye className="w-4 h-4" />
// </button>
// <button className="p-2 text-gray-400 hover:text-blue-600" aria-label="Просмотр">
//   <Edit className="w-4 h-4" />
// </button>

// And the same for green ones

content = content.replace(
  /<button className="p-2 text-gray-400 hover:text-blue-600" aria-label="Просмотр">\s*<Edit/g,
  '<button className="p-2 text-gray-400 hover:text-blue-600" aria-label="Редактировать">\n                      <Edit'
);

content = content.replace(
  /<button className="p-2 text-gray-400 hover:text-green-600" aria-label="Просмотр">\s*<Edit/g,
  '<button className="p-2 text-gray-400 hover:text-green-600" aria-label="Редактировать">\n                      <Edit'
);

fs.writeFileSync(file, content);
