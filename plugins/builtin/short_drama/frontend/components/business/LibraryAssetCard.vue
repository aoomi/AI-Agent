<script setup lang="ts">
import BaseButton from "../base/BaseButton.vue";
import StatusPill from "../base/StatusPill.vue";

type LibraryAsset = { project:string; name:string; category:string; episode:string; src:string };
defineProps<{ item:LibraryAsset }>();
defineEmits<{ preview:[src:string]; details:[]; apply:[]; drag:[] }>();
</script>

<template>
  <article draggable @dragstart="$emit('drag')">
    <BaseButton class="media" @click="$emit('preview',item.src)"><img :src="item.src"></BaseButton>
    <div class="asset-meta"><StatusPill class="blue">{{item.category}}</StatusPill><small>{{item.episode}}</small></div>
    <h3>{{item.name}}</h3><p>{{item.project}} · 已自动归档</p>
    <div class="card-actions"><BaseButton @click="$emit('details')">详情</BaseButton><BaseButton @click="$emit('apply')">应用到</BaseButton></div>
  </article>
</template>
