<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import FileModeView from './FileModeView.vue'
import KBModeView from './KBModeView.vue'
import AnalysisModeView from './AnalysisModeView.vue'

const props = defineProps<{
  mode: string
}>()

const route = useRoute()

const mode = computed(() => {
  const m = route.path.match(/\/mode\/(\w+)/)
  return m ? m[1] : props.mode
})
</script>

<template>
  <FileModeView v-if="mode === 'file'" />
  <KBModeView v-else-if="mode === 'kb'" />
  <AnalysisModeView v-else-if="mode === 'analysis'" />
</template>
