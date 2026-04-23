"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const VapidSubjectField_1 = require("../../src/mobile/components/VapidSubjectField");
const tests = [];
function test(name, fn) {
    tests.push({ name, fn });
}
test('normalizeVapidSubject trims surrounding whitespace', () => {
    strict_1.default.equal((0, VapidSubjectField_1.normalizeVapidSubject)('  mailto:admin@example.com  '), 'mailto:admin@example.com');
});
test('isValidVapidSubject accepts mailto subjects', () => {
    strict_1.default.equal((0, VapidSubjectField_1.isValidVapidSubject)('mailto:admin@example.com'), true);
});
test('isValidVapidSubject accepts https subjects', () => {
    strict_1.default.equal((0, VapidSubjectField_1.isValidVapidSubject)('https://example.com/contact'), true);
});
test('isValidVapidSubject rejects unsupported schemes and blanks', () => {
    strict_1.default.equal((0, VapidSubjectField_1.isValidVapidSubject)('ftp://example.com'), false);
    strict_1.default.equal((0, VapidSubjectField_1.isValidVapidSubject)('   '), false);
    strict_1.default.equal((0, VapidSubjectField_1.isValidVapidSubject)('admin@example.com'), false);
});
let passed = 0;
let failed = 0;
for (const current of tests) {
    try {
        current.fn();
        console.log(`  ok  ${current.name}`);
        passed += 1;
    }
    catch (error) {
        console.error(`  FAIL ${current.name}`);
        console.error(`    ${error.message}`);
        failed += 1;
    }
}
console.log(`\nvapidSubjectField.spec - ${passed}/${passed + failed} passed${failed ? ` (${failed} failed)` : ''}`);
if (failed > 0) {
    process.exit(1);
}
