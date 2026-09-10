const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const array = value => Array.isArray(value) ? value : [];
const number = value => Number.isFinite(value) ? String(Number(value.toFixed(4))) : '—';
const label = factor => escapeHtml(factor.zh || factor.en || factor.id || '未命名因素');
const list = (title, factors) => array(factors).length
  ? '<p class="test"><strong>'+title+'：</strong>'+factors.map(label).join(' · ')+'</p>' : '';

function evidenceList(factors) {
  return '<ol class="ev">'+array(factors).map(f => {
    const direction = f.direction === 'counter' ? '反向因素' : f.direction === 'pro' ? '正向因素' : '待确认因素';
    const swing = Number.isFinite(f.maximum_swing) ? f.maximum_swing
      : Array.isArray(f.swing) && f.swing.every(Number.isFinite) ? Math.max(...f.swing.map(Math.abs)) : null;
    return '<li>'+label(f)+' <span class="tiny">'+direction
      +(swing === null ? '' : ' · 最大影响 '+number(swing))
      +(f.look_for || f.evidence ? ' · 找：'+escapeHtml(f.look_for || f.evidence) : '')+'</span></li>';
  }).join('')+'</ol>';
}

export function renderScoreResult(data) {
  if (!data || !Array.isArray(data.stages) || data.stages.length === 0) throw new Error('判断服务没有返回有效阶段，请重新尝试。');
  let html = '<div class="card"><h4>总体仍需人工判断</h4>'
    +'<p class="test">以下结果用于整理证据和查看当前模型的情景范围，不能自动得出法律结论。</p>'
    +(data.overall_reason || data.reason ? '<p class="tiny">'+escapeHtml(data.overall_reason || data.reason)+'</p>' : '')+'</div>';
  for (const stage of data.stages) {
    if (!stage || typeof stage !== 'object') throw new Error('判断服务返回的阶段格式不完整。');
    html += '<div class="card"><div class="head"><span class="sid">'+escapeHtml(stage.stage)
      +'</span><span class="stt">'+escapeHtml(stage.zh || stage.en)+'</span></div>';
    const numeric = stage.test_type === 'balancing'
      && !['incomplete','unassigned'].includes(stage.weights)
      && Number.isFinite(stage.score_low) && Number.isFinite(stage.score_high)
      && stage.score_low <= stage.score_high;
    if (numeric) {
      const coverage = Number.isFinite(stage.evidence_resolved) ? Math.min(1,Math.max(0,stage.evidence_resolved)) : 0;
      const scale = Math.max(1, Math.abs(stage.score_low), Math.abs(stage.score_high));
      const left = (stage.score_low/scale+1)*50, right = (stage.score_high/scale+1)*50;
      const status = !coverage ? '证据不足，无法判断' : stage.interval_decides ? '当前启发式分档稳定，仍需人工判断' : '当前情景范围尚不能稳定分档';
      html += '<p class="test"><strong>'+status+'</strong></p>'
        +'<p class="test">启发式情景区间 <strong>'+number(stage.score_low)+' … '+number(stage.score_high)
        +'</strong> · 已确认事实 '+Math.round(coverage*100)+'%</p>'
        +'<p class="tiny">包含尚未确认的正反因素及权重范围；区间不表示胜诉概率。</p>'
        +'<div class="rng2" role="img" aria-label="启发式情景区间 '+number(stage.score_low)+' 至 '+number(stage.score_high)+'">'
        +'<div class="rngmid" style="left:50%"></div><div class="rngspan" style="left:'+left.toFixed(2)+'%;width:'+(right-left).toFixed(2)+'%;background:var(--ink3)"></div></div>';
    } else if (stage.test_type === 'balancing') {
      html += '<p class="test"><strong>'+(stage.weights === 'unassigned' ? '数值权重未赋值' : '数值权重不完整，暂不计算')+'</strong></p>'
        +'<p class="test">先查看事实清单。学说权重的赋值与经验校准是不同事项。</p>';
    } else {
      const status = {
        undetermined:'证据或模型信息不足，无法判断',
        'manual-checklist':'需要人工判断：以下为法律清单',
        unsupported:'该测试结构尚不支持自动判断',
        'not-engaged':'当前记录下，该阶段未触发',
        'clause-enforced':'按该阶段已编码规则适用条款；总体仍需判断',
        'override-applies':'按该阶段已编码规则触发例外；总体仍需判断',
        'clause-overridden':'按该阶段已编码规则触发例外；总体仍需判断',
        'departure-permitted':'按该阶段已编码规则允许偏离；总体仍需判断',
      }[stage.result] || '需要人工判断：该阶段只提供已编码的事实与规则';
      html += '<p class="test"><strong>'+status+'</strong></p>'
        +'<p class="tiny">“存在／不存在”记录事实；必要项、路径、排除项及例外须结合阶段规则判断，系统不自动作法律结论。</p>';
    }
    if (stage.reason || stage.note || stage.effect) html += '<p class="tiny">'+escapeHtml(stage.reason || stage.note || stage.effect)+'</p>';
    html += list('已记录存在',stage.factors_present || stage.gateways_open)
      + list('已记录存在的反向因素',stage.factors_against)
      + list('已记录不存在',stage.factors_absent)
      + list('尚未确认',stage.unresolved);
    if (array(stage.next_evidence).length) html += '<p class="test"><strong>下一步取证</strong></p>'+evidenceList(stage.next_evidence);
    if (stage.caveat) html += '<p class="tiny">'+escapeHtml(stage.caveat)+'</p>';
    html += '</div>';
  }
  if (array(data.priority_evidence).length) html += '<div class="card"><h4>全模块取证优先级</h4>'+evidenceList(data.priority_evidence)+'</div>';
  return html;
}

// Ignore late successes and failures after a new choice or a view change.
export function createScoreUpdater({fetchScore,isCurrent,onLoading,onResult,onError}) {
  let sequence = 0, controller;
  return async facts => {
    const request = ++sequence;
    controller?.abort();
    controller = new AbortController();
    const current = () => request === sequence && isCurrent();
    if (!current()) return;
    onLoading();
    try {
      const data = await fetchScore({...facts},controller.signal);
      if (current()) onResult(renderScoreResult(data));
    } catch (error) {
      if (current()) onError(error instanceof Error ? error.message : '判断请求失败，请重试。');
    }
  };
}
