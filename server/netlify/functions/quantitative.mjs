// Both runtimes interpret legal_quant/models.json. There are no model formulas here.
import catalogue from '../../../legal_quant/models.json' with { type: 'json' };
import sourceLedger from '../../../legal_quant/sources.json' with { type: 'json' };

const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
const record = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const finite = value => typeof value === 'number' && Number.isFinite(value);
const forbidden = new Set(['__proto__', 'prototype', 'constructor']);

export class QuantitativeError extends Error {
  constructor(message, status = 400) { super(message); this.status = status; }
}
const reject = message => { throw new QuantitativeError(message); };

// JSON.parse validates syntax but otherwise silently keeps the last duplicate
// key. Scan its already-valid token stream so an input has one unambiguous value.
export function parseQuantitativeJSON(raw) {
  let value;
  try { value = JSON.parse(raw); }
  catch { reject('需要有效 JSON；不能使用 NaN 或 Infinity。'); }
  const stack = [];
  const tokens = /"(?:\\[\s\S]|[^"\\])*"|[{}\[\],:]/g;
  for (const match of raw.matchAll(tokens)) {
    const token = match[0];
    if (token === '{') stack.push({ keys: new Set(), keyExpected: true });
    else if (token === '[') stack.push({ keys: null });
    else if (token === '}' || token === ']') stack.pop();
    else {
      const frame = stack.at(-1);
      if (token === ',' && frame?.keys) frame.keyExpected = true;
      else if (token[0] === '"' && frame?.keys && frame.keyExpected) {
        const key = JSON.parse(token);
        if (frame.keys.has(key)) reject(`JSON 包含重复字段：${key}`);
        frame.keys.add(key);
        frame.keyExpected = false;
      }
    }
  }
  return value;
}

function checkedNumber(value) {
  if (!finite(value)) reject('计算要求有限数值；请检查输入、分母和金额规模。');
  return value;
}

function lookup(scope, path) {
  if (typeof path !== 'string' || path.length > 300) reject('无效的公式变量路径。');
  let value = scope;
  for (const key of path.split('.')) {
    if (forbidden.has(key) || value == null || !own(value, key)) reject(`公式变量不存在：${path}`);
    value = value[key];
  }
  return value;
}

// Trusted catalogue AST only. User input cannot provide or replace expressions.
export function evaluateExpression(expression, scope, depth = 0) {
  if (depth > 64) reject('公式嵌套超过允许范围。');
  const evaluate = (value, nextScope = scope) => evaluateExpression(value, nextScope, depth + 1);
  if (expression === null || typeof expression === 'string' || typeof expression === 'boolean') return expression;
  if (typeof expression === 'number') return checkedNumber(expression);
  if (Array.isArray(expression)) return expression.map(value => evaluate(value));
  if (!record(expression)) reject('无效的公式结构。');
  if (own(expression, 'var')) return lookup(scope, expression.var);
  const { op } = expression;
  if (op === 'if') {
    const condition = evaluate(expression.condition);
    if (typeof condition !== 'boolean') reject('条件表达式必须返回布尔值。');
    return evaluate(condition ? expression.then : expression.else);
  }
  if (op === 'map') {
    const items = evaluate(expression.items);
    if (!Array.isArray(items) || items.length > 256) reject('公式数组超出允许范围。');
    return items.map((item, index) => evaluate(expression.value, { ...scope, item, index }));
  }
  if (!Array.isArray(expression.args)) reject(`公式操作 ${op} 缺少参数。`);
  const args = expression.args.map(value => evaluate(value));
  if (op === 'and' || op === 'or') {
    if (args.some(value => typeof value !== 'boolean')) reject('逻辑操作要求布尔值。');
    return op === 'and' ? args.every(Boolean) : args.some(Boolean);
  }
  if (op === 'eq' || op === 'ne') {
    if (args.length !== 2) reject('相等比较要求两个参数。');
    return op === 'eq' ? args[0] === args[1] : args[0] !== args[1];
  }
  if (op === 'at') {
    if (args.length !== 2 || !Array.isArray(args[0]) || !Number.isInteger(args[1]) ||
        args[1] < 0 || args[1] >= args[0].length) reject('数组索引必须指向已有项目。');
    return args[0][args[1]];
  }
  if (['sum', 'min', 'max', 'argmin'].includes(op)) {
    const values = args.length === 1 && Array.isArray(args[0]) ? args[0] : args;
    if ((op !== 'sum' && !values.length) || (op === 'sum' && (args.length !== 1 || !Array.isArray(args[0])))) {
      reject('聚合操作缺少有效数组。');
    }
    values.forEach(checkedNumber);
    if (op === 'argmin') {
      const minimum = Math.min(...values);
      return values.flatMap((value, index) => value === minimum ? [index] : []);
    }
    return checkedNumber(op === 'sum' ? values.reduce((a, b) => a + b, 0) :
      op === 'min' ? Math.min(...values) : Math.max(...values));
  }
  args.forEach(checkedNumber);
  if (op === 'abs') {
    if (args.length !== 1) reject('abs 要求一个参数。');
    return Math.abs(args[0]);
  }
  if (['lt', 'le', 'gt', 'ge'].includes(op)) {
    if (args.length !== 2) reject('大小比较要求两个参数。');
    return ({ lt: () => args[0] < args[1], le: () => args[0] <= args[1],
      gt: () => args[0] > args[1], ge: () => args[0] >= args[1] })[op]();
  }
  if (!args.length) reject('算术操作缺少参数。');
  let result;
  switch (op) {
    case 'add': result = args.reduce((a, b) => a + b, 0); break;
    case 'mul': result = args.reduce((a, b) => a * b, 1); break;
    case 'sub':
      if (args.length !== 2) reject('sub 要求两个参数。');
      result = args[0] - args[1]; break;
    case 'div':
      if (args.length !== 2 || args[1] === 0) reject('分母不能为零。');
      result = args[0] / args[1]; break;
    case 'pow':
      if (args.length !== 2) reject('pow 要求两个参数。');
      result = Math.pow(args[0], args[1]); break;
    default: reject(`不支持的公式操作：${op}`);
  }
  return checkedNumber(result);
}

function validateFields(fields, inputs, prefix = 'inputs') {
  if (!record(inputs)) reject(`${prefix} 必须是对象。`);
  const ids = new Set(fields.map(field => field.id));
  for (const key of Object.keys(inputs)) {
    if (forbidden.has(key) || !ids.has(key)) reject(`${prefix}.${key}：未知输入字段。`);
  }
  for (const field of fields) {
    const label = `${prefix}.${field.id}`;
    if (!own(inputs, field.id)) reject(`${label}：缺少输入；空白不能作为零。`);
    const value = inputs[field.id];
    if (field.type === 'number' || field.type === 'integer') {
      if (!finite(value) || (field.type === 'integer' && !Number.isSafeInteger(value))) {
        reject(`${label}：必须是有限${field.type === 'integer' ? '整数' : '数值'}。`);
      }
      if (own(field, 'min') && value < field.min) reject(`${label}：小于最小值 ${field.min}。`);
      if (own(field, 'max') && value > field.max) reject(`${label}：大于最大值 ${field.max}。`);
      if (own(field, 'exclusiveMinimum') && value <= field.exclusiveMinimum) reject(`${label}：须大于 ${field.exclusiveMinimum}。`);
      if (own(field, 'exclusiveMaximum') && value >= field.exclusiveMaximum) reject(`${label}：须小于 ${field.exclusiveMaximum}。`);
    } else if (field.type === 'string') {
      if (typeof value !== 'string' || !value.trim() || value.length > 2000) reject(`${label}：需要非空文字，最多2000字。`);
    } else if (field.type === 'number_array' || field.type === 'object_array') {
      if (!Array.isArray(value) || value.length < (field.minItems ?? 1) || value.length > Math.min(field.maxItems ?? 256, 256)) {
        reject(`${label}：数组长度不符合要求。`);
      }
      value.forEach((item, index) => {
        if (field.type === 'object_array') validateFields(field.items, item, `${label}[${index}]`);
        else {
          if (!finite(item) || (own(field, 'min') && item < field.min) || (own(field, 'max') && item > field.max)) {
            reject(`${label}[${index}]：数值超出允许范围。`);
          }
        }
      });
    } else reject(`${label}：未知字段类型。`);
    if (field.enum && !field.enum.includes(value)) reject(`${label}：必须选择允许的值。`);
  }
}

function normalizeContext(value, model) {
  if (value === undefined) value = {};
  if (!record(value)) reject('context 必须是对象。');
  const allowed = ['jurisdiction', 'as_of', 'input_basis', 'sources', 'applicability'];
  if (Object.keys(value).some(key => !allowed.includes(key))) reject('context 包含未知字段。');
  const context = { jurisdiction: 'HK', as_of: null, input_basis: 'hypothetical',
    sources: {}, applicability: 'unreviewed', ...value };
  if (typeof context.jurisdiction !== 'string' || !context.jurisdiction.trim() || context.jurisdiction.length > 100) {
    reject('jurisdiction 必须是非空文字。');
  }
  if (context.as_of !== null) {
    if (typeof context.as_of !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(context.as_of) ||
        Number(context.as_of.slice(0, 4)) < 1 || !Number.isFinite(Date.parse(context.as_of)) ||
        new Date(context.as_of).toISOString().slice(0, 10) !== context.as_of) reject('as_of 必须是有效 YYYY-MM-DD 日期或 null。');
  }
  if (!['hypothetical', 'case_data'].includes(context.input_basis)) reject('input_basis 必须是 hypothetical 或 case_data。');
  if (!['unreviewed', 'externally_assessed'].includes(context.applicability)) reject('applicability 必须是 unreviewed 或 externally_assessed。');
  if (!record(context.sources)) reject('sources 必须是字段与来源说明的映射。');
  const ids = new Set(model.fields.map(field => field.id));
  for (const [key, source] of Object.entries(context.sources)) {
    if (!ids.has(key) || typeof source !== 'string' || !source.trim() || source.length > 4000) reject(`sources.${key}：来源字段无效。`);
  }
  if (context.input_basis === 'case_data') {
    for (const field of model.fields) {
      if (!own(context.sources, field.id)) reject(`sources.${field.id}：案件数据须说明每项输入的来源。`);
    }
  }
  return context;
}

export function quantitativeCatalogue() {
  return { version: catalogue.schema_version, models: structuredClone(catalogue.models),
    sources: structuredClone(sourceLedger.sources) };
}

export function evaluateQuantitative(request) {
  if (!record(request)) reject('请求必须是对象。');
  if (Object.keys(request).some(key => !['model_id', 'model_version', 'inputs', 'context'].includes(key))) {
    reject('只允许 model_id、model_version、inputs 和 context；公式不能由请求替换。');
  }
  if (typeof request.model_id !== 'string' || !request.model_id) reject('model_id 必须指定一个模型。');
  const model = catalogue.models.find(item => item.id === request.model_id);
  if (!model) throw new QuantitativeError('未找到所指定的量化模型。', 404);
  if (request.model_version !== model.version) throw new QuantitativeError('模型版本不匹配，请重新载入模型。', 409);
  validateFields(model.fields, request.inputs);
  const context = normalizeContext(request.context, model);
  const results = {};
  const scope = { input: request.inputs, out: results };
  for (const constraint of model.constraints || []) {
    if (evaluateExpression(constraint.expression, scope) !== true) reject(constraint.message);
  }
  const steps = [];
  for (const output of model.outputs) {
    const value = evaluateExpression(output.expression, scope);
    results[output.id] = value;
    steps.push({ id: output.id, label: output.label, unit: output.unit, formula: output.formula, value });
  }
  return {
    model_id: model.id, model_version: model.version, category: model.category,
    output_kind: model.output_kind, context, inputs: structuredClone(request.inputs), results, steps,
    source_ids: [...model.source_ids], legal_status: model.legal_status,
    analysis_layer: model.analysis_layer, formula_authority: model.formula_authority,
    assumptions: model.assumptions, limitations: model.limitations,
    required_legal_findings: model.required_legal_findings,
    legal_conclusion: null, applicability_status: context.applicability,
  };
}

export function quantitativeRequest(request) {
  try { return { status: 200, body: evaluateQuantitative(request) }; }
  catch (error) {
    if (!(error instanceof QuantitativeError)) throw error;
    return { status: error.status, body: { error: error.message, result: 'invalid-input', legal_conclusion: null } };
  }
}

export const quantitativeTools = [
  { name: 'list_quantitative_models',
    description: 'List legal-standard models and supporting quantitative analysis with typed inputs, formulas, source jurisdictions and formula authority. Distinguishes judicial heuristics from project formalisation; calculations are not legal findings.',
    inputSchema: { type: 'object', additionalProperties: false, properties: {} } },
  { name: 'evaluate_quantitative_model',
    description: 'Calculate one fixed versioned model using explicit values and provenance. Missing values are rejected, never zero. Case data require source notes for every input; applicability is an external assertion, never certified by the calculation. Returns calculation steps and no legal conclusion.',
    inputSchema: { type: 'object', additionalProperties: false, required: ['model_id', 'model_version', 'inputs'],
      properties: {
        model_id: { type: 'string', enum: catalogue.models.map(model => model.id) },
        model_version: { type: 'string', enum: ['1'] },
        inputs: { type: 'object', description: 'Exact fields for this model from list_quantitative_models; no missing or extra fields.' },
        context: { type: 'object', additionalProperties: false, properties: {
          jurisdiction: { type: 'string' }, as_of: { type: ['string', 'null'], description: 'Context date only, not a request for historical law.' },
          input_basis: { type: 'string', enum: ['hypothetical', 'case_data'] },
          sources: { type: 'object', additionalProperties: { type: 'string' } },
          applicability: { type: 'string', enum: ['unreviewed', 'externally_assessed'] },
        } },
      } } },
];
