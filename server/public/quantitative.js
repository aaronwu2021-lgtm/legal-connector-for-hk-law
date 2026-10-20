'use strict';

(() => {
  const VERSION = '1';
  const $ = id => document.getElementById(id);
  const state = {
    models: [], sources: [], model: null, fields: new Map(), sourcesByField: new Map(),
    revision: 0, request: null, result: null,
  };
  const categoryLabels = {
    money: '金额计算', monetary: '金额计算', damages: '金额计算', amount: '金额计算',
    evidence: '事实与证据', action: '行动选择', decision: '行动选择',
    principles: '原则权衡', principle: '原则权衡', balancing: '原则权衡',
    market: '市场结构', policy: '执法与政策', enforcement: '执法与政策',
  };
  const kindLabels = {
    monetary_calculation: '金额计算', judicial_calculation: '司法金额计算',
    expert_evidence: '专家证据模型', theoretical_model: '理论模型',
    decision_support: '行动决策工具', policy_model: '政策分析模型',
    market_indicator: '市场结构指标', economic_model: '经济分析模型',
    economic_comparison: '经济分析 · 预防措施比较',
    theoretical_weight_ratio: '理论模型 · 原则权重',
    conditional_hypothesis_probability: '证据分析 · 条件概率',
    policy_benchmark: '理论模型 · 执法政策',
    alternative_cost_comparison: '经济分析 · 方案成本',
    reservation_value_range: '决策模型 · 诉讼与和解',
    conditional_loss_amount: '条件金额计算 · 适用规则须审查',
    conditional_chance_value: '条件价值计算 · 机会损失须获法律承认',
    conditional_present_value: '精算金额计算 · 参数须核对',
    conditional_counterfactual_loss: '专家证据模型 · 反事实损失',
    market_structure_indicator: '结构指标 · 市场集中度',
  };

  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = String(text);
    if (className) node.className = className;
    return node;
  }
  function readable(value) {
    return typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  }
  function listInto(target, values) {
    target.replaceChildren(...(values || []).map(value => element('li', readable(value))));
  }
  function report(id, text, error = false) {
    $(id).textContent = text;
    $(id).dataset.error = String(error);
  }
  function invalidate(message = '') {
    state.revision += 1;
    state.request?.abort();
    state.request = null;
    state.result = null;
    $('calculate').disabled = false;
    $('calculate').textContent = '查看计算步骤';
    $('results').hidden = true;
    $('result-cards').replaceChildren();
    $('calculation-steps').replaceChildren();
    report('form-status', message);
  }
  function option(value, label) {
    const node = element('option', label);
    node.value = value;
    return node;
  }
  function fieldChildren(field) {
    if (Array.isArray(field.items)) return field.items;
    return field.items?.fields || [];
  }
  function sourceDescription(field) {
    return `${field.label}的证据或假设来源`;
  }
  function renderFields() {
    state.fields.clear();
    state.sourcesByField.clear();
    $('fields').replaceChildren();
    state.model.fields.forEach((field, index) => {
      const isArray = field.type === 'number_array' || field.type === 'object_array';
      const container = element('div', undefined, `field${isArray ? ' is-complex' : ''}`);
      const control = element('div', undefined, 'control');
      const id = `field-${index}`;
      const label = element('label', `${index + 1}. ${field.label}`, 'field-title');
      label.htmlFor = id;
      control.append(label, element('span', `单位：${field.unit || '无量纲'}`, 'field-unit'));
      if (field.description) {
        const description = element('p', field.description, 'field-description');
        description.id = `${id}-description`;
        control.append(description);
      }
      let input;
      if (isArray) {
        input = element('textarea');
        input.rows = field.type === 'object_array' ? 10 : 4;
        input.spellcheck = false;
        const schema = element('details', undefined, 'array-schema');
        schema.append(element('summary', '填写格式与字段说明'));
        if (field.type === 'object_array') {
          const descriptions = fieldChildren(field).map(child =>
            `${child.id}：${child.label}；单位 ${child.unit || '无量纲'}${child.description ? `；${child.description}` : ''}`
          );
          schema.append(element('pre', descriptions.join('\n')));
        } else {
          schema.append(element('p', '填写数字数组，例如 [40, 30, 20, 10]。数组各项使用本字段注明的单位。', 'help'));
        }
        schema.append(element('span', '本模型教学格式示例：', 'help'));
        schema.append(element('pre', JSON.stringify(state.model.example_inputs?.[field.id] ?? [], null, 2)));
        control.append(schema);
      } else if (field.enum) {
        input = element('select');
        input.append(option('', '请选择'));
        field.enum.forEach(value => input.append(option(String(value), String(value))));
      } else {
        input = element('input');
        input.type = ['number', 'integer'].includes(field.type) ? 'number' : 'text';
        if (input.type === 'number') {
          input.step = field.type === 'integer' ? '1' : 'any';
          if (field.min !== undefined) input.min = String(field.min);
          if (field.max !== undefined) input.max = String(field.max);
        }
      }
      input.id = id;
      input.name = field.id;
      input.required = true;
      if (field.description) input.setAttribute('aria-describedby', `${id}-description`);
      control.append(input);
      const sourceControl = element('div', undefined, 'control source-control');
      const sourceLabel = element('label', '来源 / 假设依据');
      sourceLabel.htmlFor = `${id}-source`;
      const source = element('input');
      source.type = 'text';
      source.id = `${id}-source`;
      source.maxLength = 4000;
      source.placeholder = '如：报告第 12 页，2026-10-01；或教学假设';
      source.setAttribute('aria-label', sourceDescription(field));
      sourceControl.append(sourceLabel, source, element('span', '填写出处及定位；估计值同时注明估计方法。', 'help'));
      container.append(control, sourceControl);
      $('fields').append(container);
      state.fields.set(field.id, input);
      state.sourcesByField.set(field.id, source);
    });
    updateBasis();
  }
  function renderSources() {
    const ids = new Set(state.model.source_ids || []);
    const sources = state.sources.filter(source => ids.has(source.id));
    $('model-sources').replaceChildren(...sources.map(source => {
      const item = element('li');
      let title = element('span', source.title, 'source-title');
      try {
        const url = new URL(source.url);
        if (['https:', 'http:'].includes(url.protocol)) {
          title = element('a', source.title, 'source-title');
          title.href = url.href;
          title.target = '_blank';
          title.rel = 'noopener noreferrer';
        }
      } catch { /* Invalid URLs remain plain text. */ }
      item.append(title);
      const metadata = [
        source.jurisdiction ? `来源法域：${readable(source.jurisdiction)}` : '',
        source.pin ? `定位：${readable(source.pin)}` : '',
        source.verification ? `核验：${readable(source.verification)}` : '',
      ].filter(Boolean);
      item.append(element('p', metadata.join(' · '), 'source-meta'));
      if (source.note) item.append(element('p', source.note, 'source-meta'));
      return item;
    }));
    if (!sources.length) $('model-sources').append(element('li', '本模型尚未附可展示的来源记录。'));
  }
  function selectModel(modelId) {
    const model = state.models.find(item => item.id === modelId);
    if (!model) throw new Error('未找到该模型。');
    invalidate();
    state.model = model;
    $('model').value = model.id;
    $('model-title').textContent = model.title;
    $('model-question').textContent = model.question;
    $('model-kind').textContent = kindLabels[model.output_kind] || model.output_kind;
    $('model-status').textContent = readable(model.legal_status || '');
    $('formula').textContent = model.formula_summary;
    listInto($('assumptions'), model.assumptions);
    listInto($('limitations'), model.limitations);
    listInto($('legal-findings'), model.required_legal_findings);
    $('input-basis').value = 'hypothetical';
    $('applicability').value = 'unreviewed';
    renderFields();
    renderSources();
    report('file-status', '');
  }
  function populateModels(category, selected) {
    const models = state.models.filter(model => model.category === category);
    $('model').replaceChildren(...models.map(model => option(model.id, model.title)));
    if (models.length) selectModel(selected || models[0].id);
  }
  function updateBasis() {
    const caseData = $('input-basis').value === 'case_data';
    $('basis-notice').textContent = caseData
      ? '当前为案件数据。每个字段都须填写可定位的来源；转换后请逐项核对数据和出处。程序不核实来源文字的真实性。'
      : '当前为教学假设。示例数值不代表法律标准或真实案件事实。';
    for (const source of state.sourcesByField.values()) source.required = caseData;
  }
  function validateField(value, field, path = field.label) {
    const fail = message => { throw new Error(`${path}：${message}`); };
    if (field.type === 'number' || field.type === 'integer') {
      if (typeof value !== 'number' || !Number.isFinite(value)) fail('请输入有限数字。');
      if (field.type === 'integer' && !Number.isSafeInteger(value)) fail('须为可精确表示的安全整数。');
      if (field.min !== undefined && value < field.min) fail(`不能小于 ${field.min}。`);
      if (field.max !== undefined && value > field.max) fail(`不能大于 ${field.max}。`);
      if (field.exclusiveMinimum !== undefined && value <= field.exclusiveMinimum) fail(`须大于 ${field.exclusiveMinimum}。`);
      if (field.exclusiveMaximum !== undefined && value >= field.exclusiveMaximum) fail(`须小于 ${field.exclusiveMaximum}。`);
    } else if (field.type === 'string') {
      if (typeof value !== 'string' || !value.trim() || value.length > 2000) fail('请输入 2000 字以内的非空文字。');
      if (field.enum && !field.enum.includes(value)) fail('请使用列出的选项。');
    } else if (['number_array', 'object_array'].includes(field.type)) {
      if (!Array.isArray(value)) fail('请填写 JSON 数组。');
      if (value.length < (field.minItems ?? 1)) fail(`至少需要 ${field.minItems ?? 1} 项。`);
      if (value.length > Math.min(field.maxItems ?? 256, 256)) fail(`最多允许 ${Math.min(field.maxItems ?? 256, 256)} 项。`);
      value.forEach((entry, index) => {
        const pathEntry = `${path}第 ${index + 1} 项`;
        if (field.type === 'number_array') {
          const itemSchema = !Array.isArray(field.items) && field.items ? field.items : { min: field.min, max: field.max };
          validateField(entry, { ...itemSchema, type: 'number' }, pathEntry);
        } else {
          if (!entry || typeof entry !== 'object' || Array.isArray(entry)) fail(`第 ${index + 1} 项须为对象。`);
          const children = fieldChildren(field);
          const names = new Set(children.map(child => child.id));
          if (Object.keys(entry).some(key => !names.has(key))) fail(`第 ${index + 1} 项含未识别的字段。`);
          children.forEach(child => validateField(entry[child.id], child, `${pathEntry} / ${child.label}`));
        }
      });
    } else fail('模型包含尚不支持的字段类型。');
    if (field.enum && !field.enum.includes(value)) fail('请使用列出的选项。');
  }
  function normalizeContext(value, model) {
    if (value === undefined) value = {};
    if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('分析背景 context 须为对象。');
    const allowed = new Set(['jurisdiction', 'as_of', 'input_basis', 'sources', 'applicability']);
    if (Object.keys(value).some(key => !allowed.has(key))) throw new Error('分析背景 context 含未识别的字段。');
    const context = {
      jurisdiction: 'HK', as_of: null, input_basis: 'hypothetical',
      sources: {}, applicability: 'unreviewed', ...value,
    };
    if (typeof context.jurisdiction !== 'string' || !context.jurisdiction.trim() || context.jurisdiction.length > 100) throw new Error('请填写拟适用法域（100 字以内）。');
    if (context.as_of !== null) {
      if (typeof context.as_of !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(context.as_of) || Number(context.as_of.slice(0, 4)) < 1) throw new Error('分析基准日须为 YYYY-MM-DD 或留空（null）。');
      const date = new Date(`${context.as_of}T00:00:00Z`);
      if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== context.as_of) throw new Error('分析基准日无效。');
    }
    if (!['hypothetical', 'case_data'].includes(context.input_basis)) throw new Error('输入依据无效。');
    if (!['unreviewed', 'externally_assessed'].includes(context.applicability)) throw new Error('法律适用审查状态无效。');
    if (!context.sources || typeof context.sources !== 'object' || Array.isArray(context.sources)) throw new Error('缺少逐项来源 sources。');
    const names = new Set(model.fields.map(field => field.id));
    if (Object.keys(context.sources).some(key => !names.has(key))) throw new Error('来源记录含未识别的字段。');
    model.fields.forEach(field => {
      const source = context.sources[field.id];
      if (source !== undefined && (typeof source !== 'string' || !source.trim() || source.length > 4000)) throw new Error(`${field.label}的来源须为 4000 字以内的非空文字。`);
      if (context.input_basis === 'case_data' && source === undefined) throw new Error(`${field.label}：案件数据须填写每项输入的来源。`);
    });
    return context;
  }
  function validateCase(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('输入文件须为 JSON 对象。');
    const allowedRequestKeys = new Set(['model_id', 'model_version', 'inputs', 'context']);
    if (Object.keys(data).some(key => !allowedRequestKeys.has(key))) throw new Error('输入文件含未识别的请求字段；仅支持 model_id、model_version、inputs 和 context。');
    if (data.model_version !== VERSION) throw new Error('本工作台仅支持 model_version 为字符串 "1" 的输入。');
    const model = state.models.find(item => item.id === data.model_id);
    if (!model) throw new Error('输入文件的 model_id 不属于当前模型库。');
    if (!data.inputs || typeof data.inputs !== 'object' || Array.isArray(data.inputs)) throw new Error('缺少 inputs 对象。');
    const allowed = new Set(model.fields.map(field => field.id));
    if (Object.keys(data.inputs).some(key => !allowed.has(key))) throw new Error('输入包含本模型未定义的字段。');
    model.fields.forEach(field => validateField(data.inputs[field.id], field));
    data.context = normalizeContext(data.context, model);
    return model;
  }
  function readCase() {
    const inputs = {};
    const sources = {};
    state.model.fields.forEach(field => {
      const raw = state.fields.get(field.id).value.trim();
      if (!raw) throw new Error(`请填写「${field.label}」。`);
      if (field.type.endsWith('_array')) {
        try { inputs[field.id] = JSON.parse(raw); }
        catch { throw new Error(`${field.label}：JSON 格式有误，请检查引号、逗号及方括号。`); }
      } else inputs[field.id] = ['number', 'integer'].includes(field.type) ? Number(raw) : raw;
      const source = state.sourcesByField.get(field.id).value.trim();
      if (source) sources[field.id] = source;
    });
    const data = {
      model_id: state.model.id, model_version: VERSION, inputs,
      context: {
        jurisdiction: $('jurisdiction').value.trim(), as_of: $('as-of').value || null,
        input_basis: $('input-basis').value, sources, applicability: $('applicability').value,
      },
    };
    validateCase(data);
    return data;
  }
  function writeInputs(inputs, sources = {}) {
    state.model.fields.forEach(field => {
      const value = inputs[field.id];
      state.fields.get(field.id).value = value === undefined ? '' : (field.type.endsWith('_array') ? JSON.stringify(value, null, 2) : String(value));
      state.sourcesByField.get(field.id).value = sources[field.id] || '';
    });
  }
  const numberFormat = new Intl.NumberFormat('zh-Hans', { maximumSignificantDigits: 10 });
  function displayValue(value) {
    if (typeof value === 'boolean') return value ? '是' : '否';
    if (typeof value === 'number') {
      if (value !== 0 && (Math.abs(value) < 1e-6 || Math.abs(value) >= 1e14)) return value.toExponential(6);
      return numberFormat.format(value);
    }
    return readable(value);
  }
  function showResult(result, data) {
    state.result = { ...result, input_record: data };
    $('result-context').textContent = `${state.model.title} · ${data.context.jurisdiction} · ${data.context.as_of || '未记录日期'} · ${data.context.input_basis === 'hypothetical' ? '教学假设' : '案件数据'}。显示数值经适度舍入，下载文件保留计算值。`;
    $('result-applicability').textContent = result.applicability_status === 'externally_assessed'
      ? '使用者已记录程序外法律适用审查。此记录不代表程序认定；计算结果不构成法律结论。'
      : '法律适用待独立审查。计算结果不认定责任、证明标准是否满足或具体规则可适用于香港。';
    const outputMap = new Map((state.model.outputs || []).map(output => [output.id, output]));
    const steps = Array.isArray(result.steps) ? result.steps : [];
    const stepsMap = new Map(steps.map(step => [step.id, step]));
    $('result-inputs').replaceChildren(...state.model.fields.flatMap(field => {
      const term = element('dt', `${field.label}（${field.unit || '无量纲'}）`);
      const definition = element('dd', `${readable(data.inputs[field.id])}\n来源：${data.context.sources[field.id] || '未记录（教学假设）'}`);
      return [term, definition];
    }));
    $('result-cards').replaceChildren(...Object.entries(result.results || {}).map(([key, value]) => {
      const output = outputMap.get(key) || stepsMap.get(key) || {};
      const card = element('div', undefined, 'result-card');
      card.append(element('h3', output.label || key), element('p', displayValue(value), 'result-value'));
      if (output.unit) card.append(element('p', output.unit, 'result-unit'));
      if (data.model_id === 'coase' && key === 'minimum_indices' && Array.isArray(value)) {
        const names = value.map(index => data.inputs.alternatives[index]?.name).filter(Boolean);
        card.append(element('p', `对应方案：${names.join('、')}`, 'result-unit'));
      }
      return card;
    }));
    $('calculation-steps').replaceChildren(...steps.map(step => {
      const row = element('li');
      row.append(element('h4', step.label), element('div', step.formula, 'step-formula'));
      if (step.substitution) row.append(element('p', readable(step.substitution), 'step-substitution'));
      row.append(element('p', `= ${displayValue(step.value)}${step.unit ? ` ${step.unit}` : ''}`, 'step-value'));
      return row;
    }));
    listInto($('result-boundaries'), [...(result.assumptions || []), ...(result.limitations || [])]);
    listInto($('result-findings'), result.required_legal_findings);
    $('results').hidden = false;
    $('results').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  function downloadJSON(data, name) {
    const blob = new Blob([`${JSON.stringify(data, null, 2)}\n`], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = element('a');
    link.href = url;
    link.download = name;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  $('category').addEventListener('change', () => populateModels($('category').value));
  $('model').addEventListener('change', () => selectModel($('model').value));
  $('analysis-form').addEventListener('input', () => {
    invalidate('输入已改变，请重新计算。');
    report('file-status', '');
    updateBasis();
  });
  $('analysis-form').addEventListener('change', () => {
    invalidate('输入已改变，请重新计算。');
    updateBasis();
  });
  $('load-example').addEventListener('click', () => {
    invalidate('已载入教学假设。可修改后计算；这些数值均非真实案件事实。');
    $('input-basis').value = 'hypothetical';
    $('applicability').value = 'unreviewed';
    const sources = Object.fromEntries(state.model.fields.map(field => [field.id, '教学假设（synthetic）']));
    writeInputs(state.model.example_inputs || {}, sources);
    updateBasis();
  });
  $('reset').addEventListener('click', () => {
    invalidate('已清空本模型输入及上次计算结果。');
    $('input-basis').value = 'hypothetical';
    $('applicability').value = 'unreviewed';
    writeInputs({});
    updateBasis();
    report('file-status', '');
  });
  $('analysis-form').addEventListener('submit', async event => {
    event.preventDefault();
    invalidate();
    let data;
    try { data = readCase(); }
    catch (error) { report('form-status', error.message, true); return; }
    const revision = state.revision;
    const controller = new AbortController();
    state.request = controller;
    $('calculate').disabled = true;
    $('calculate').textContent = '正在计算…';
    report('form-status', '正在核对输入并计算…');
    try {
      const response = await fetch('/api/quant/evaluate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data), signal: controller.signal,
      });
      const result = await response.json();
      if (revision !== state.revision) return;
      if (!response.ok) {
        const message = typeof result.error === 'string' ? result.error : result.error?.message || result.message;
        throw new Error(message || `计算请求未成功（${response.status}）。`);
      }
      if (result.model_id !== data.model_id || result.model_version !== VERSION) throw new Error('响应模型或版本不匹配，请重新计算。');
      showResult(result, data);
      report('form-status', '计算完成。请同时查看步骤、前提及法律适用状态。');
    } catch (error) {
      if (revision === state.revision && error.name !== 'AbortError') report('form-status', error.message || '无法完成计算，请检查项目服务后重试。', true);
    } finally {
      if (revision === state.revision) {
        state.request = null;
        $('calculate').disabled = false;
        $('calculate').textContent = '查看计算步骤';
      }
    }
  });
  $('download-case').addEventListener('click', () => {
    try {
      const data = readCase();
      downloadJSON(data, `${data.model_id}-${data.context.as_of || 'undated'}-inputs.json`);
      report('file-status', '已下载输入文件。请自行妥善保存其中的案件信息。');
    } catch (error) { report('file-status', error.message, true); }
  });
  $('download-result').addEventListener('click', () => {
    if (state.result) downloadJSON(state.result, `${state.model.id}-${$('as-of').value || 'undated'}-result.json`);
  });
  $('import-case').addEventListener('click', () => $('case-file').click());
  $('case-file').addEventListener('change', async () => {
    const file = $('case-file').files?.[0];
    $('case-file').value = '';
    if (!file) return;
    const revision = state.revision;
    try {
      if (file.size > 1024 * 1024) throw new Error('输入文件过大，请使用 1 MB 以内的 JSON 文件。');
      const raw = await file.text();
      if (revision !== state.revision) { report('file-status', '读取文件期间输入已改变，请重新导入。', true); return; }
      let data;
      try { data = JSON.parse(raw); }
      catch { throw new Error('文件不是有效的 JSON，请检查格式。'); }
      const model = validateCase(data);
      $('category').value = model.category;
      populateModels(model.category, model.id);
      $('jurisdiction').value = data.context.jurisdiction;
      $('as-of').value = data.context.as_of || '';
      $('input-basis').value = data.context.input_basis;
      $('applicability').value = data.context.applicability;
      writeInputs(data.inputs, data.context.sources);
      updateBasis();
      report('file-status', `已导入「${model.title}」的输入。请核对来源并重新计算。`);
    } catch (error) { report('file-status', error.message, true); }
  });
  async function initialize() {
    try {
      const response = await fetch('/api/quant/models');
      if (!response.ok) throw new Error(`模型服务暂时不可用（${response.status}）。`);
      const catalogue = await response.json();
      if (catalogue.version !== VERSION || !Array.isArray(catalogue.models) || !catalogue.models.length) throw new Error('模型目录版本不匹配或目录为空。');
      state.models = catalogue.models;
      state.sources = catalogue.sources || [];
      const categories = [...new Set(state.models.map(model => model.category))];
      $('category').replaceChildren(...categories.map(category => option(category, categoryLabels[category] || category)));
      populateModels(categories[0]);
      $('load-status').hidden = true;
      $('workspace').hidden = false;
    } catch (error) {
      $('load-status').textContent = `${error.message} 请确认项目服务已启动，然后刷新页面。`;
    }
  }
  initialize();
})();
