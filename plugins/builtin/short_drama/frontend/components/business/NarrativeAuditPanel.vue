<script setup lang="ts">
import BaseButton from "../base/BaseButton.vue";

type AuditIssue = { location:string; description:string; suggestion:string };
type AuditRecord = {
  id:string;
  range:string;
  model:string;
  status:"pass"|"needs_fix";
  escalated:boolean;
  summary:string;
  fidelityScore:number;
  continuityScore:number;
  logicScore:number;
  complexityScore:number;
  issues:AuditIssue[];
  firstChanges?:unknown[];
  finalChanges?:unknown[];
};

defineProps<{
  title:string;
  subtitle:string;
  records:AuditRecord[];
  passed:boolean;
  running:boolean;
  canRollback:boolean;
  showComplexity?:boolean;
}>();

defineEmits<{
  regenerate:[];
  rollback:[];
  audit:[];
}>();
</script>

<template>
  <section class="narrative-audit-panel" :class="passed?'passed':'needs-fix'">
    <header>
      <div><b>{{title}}</b><span>{{subtitle}}</span></div>
      <div class="audit-panel-actions">
        <BaseButton @click="$emit('regenerate')">重新生成</BaseButton>
        <BaseButton v-if="canRollback" @click="$emit('rollback')">回退</BaseButton>
        <BaseButton :class="{danger:running}" @click="$emit('audit')">{{running?'停止审核':'重新审核'}}</BaseButton>
      </div>
    </header>
    <details>
      <summary>查看 {{records.length}} 个审核批次</summary>
      <article v-for="audit in records" :key="audit.id">
        <div>
          <strong>{{audit.range}} · {{audit.model}}</strong>
          <em :class="audit.status">{{audit.status==='pass'?'通过':(audit.firstChanges?.length||audit.finalChanges?.length)?'已自动修复':'需修复'}}</em>
          <small v-if="audit.escalated">已深度复核</small>
        </div>
        <p>{{audit.summary}}</p>
        <span>忠实度 {{audit.fidelityScore}} · 连续性 {{audit.continuityScore}} · 逻辑 {{audit.logicScore}}<template v-if="showComplexity"> · 复杂度 {{audit.complexityScore}}/10</template></span>
        <ul v-if="audit.issues.length">
          <li v-for="issue in audit.issues" :key="`${issue.location}-${issue.description}`"><b>{{issue.location}}：{{issue.description}}</b><small>已改为：{{issue.suggestion}}</small></li>
        </ul>
      </article>
    </details>
  </section>
</template>
