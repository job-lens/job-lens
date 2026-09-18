import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import ts from 'typescript';
const root = path.resolve(import.meta.dirname, '../src');
const rules = JSON.parse(fs.readFileSync(path.resolve(import.meta.dirname, '../architecture.generated.json')));
export function check(source, file) {
  const own = file.match(/^features\/([^/]+)\//)?.[1];
  const errors = [];
  if (own && !rules[own]) errors.push(`${file}: unregistered feature`);
  const ast = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  function inspect(specifier) {
    if (!specifier.startsWith('.') && !specifier.startsWith('@/')) return;
    const target = specifier.startsWith('@/') ? specifier.slice(2) : path.posix.normalize(path.posix.join(path.posix.dirname(file), specifier));
    const other = target.match(/^features\/([^/]+)(?:\/|$)/)?.[1];
    if (file.startsWith('shared/') && /^(app|features)\//.test(target)) errors.push(`${file} -> ${target}: shared boundary`);
    if (own && target.startsWith('app/')) errors.push(`${file} -> ${target}: feature imports app`);
    if (own && other && other !== own && (!rules[own]?.depends_on.includes(other) || !new RegExp(`^features/${other}/public$`).test(target))) errors.push(`${file} -> ${target}: private feature import`);
  }
  function visit(node) {
    if ((ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) && node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier)) inspect(node.moduleSpecifier.text);
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'require') errors.push(`${file}: CommonJS imports are not allowed in the ESM feature graph`);
    if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword) {
      if (!node.arguments[0] || !ts.isStringLiteral(node.arguments[0])) errors.push(`${file}: nonliteral dynamic import`);
      else inspect(node.arguments[0].text);
    }
    ts.forEachChild(node, visit);
  }
  visit(ast);
  return errors;
}
assert(check("import X from '../sop/private'", 'features/training/page.tsx').length);
assert(check("export { X } from '@/features/sop/public'", 'shared/api/x.ts').length);
assert(check("import X from '../../app/query'", 'features/training/page.tsx').length);
assert(check("export const x = 1", 'features/unregistered/page.tsx').length);
assert(check("import X from '@/features/sop'", 'features/training/page.tsx').length);
assert(check("const X = require('@/features/sop/private')", 'features/training/page.tsx').length);
assert.equal(check("import X from '@/shared/api/client'", 'features/training/page.tsx').length, 0);
function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)]);
}
const errors = walk(root).filter(f => /\.[jt]sx?$/.test(f) && !/\.d\.ts$|\.test\.|test\//.test(f)).flatMap(f => check(fs.readFileSync(f, 'utf8'), path.relative(root, f).split(path.sep).join('/')));
if (errors.length) throw new Error(errors.join('\n'));
console.log('Frontend architecture boundaries and negative fixtures: PASS');
