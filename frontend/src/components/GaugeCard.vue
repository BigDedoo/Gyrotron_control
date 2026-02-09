<script setup lang="ts">
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui'
import { type Component } from 'vue'

defineProps<{
  title: string
  value: number
  unit?: string
  icon?: Component
}>()
</script>

<template>
  <Card class="rounded-2xl">
    <CardHeader class="pb-2">
      <CardTitle class="text-sm font-medium flex items-center gap-2">
        <component :is="icon" v-if="icon" class="size-4" />
        {{ title }}
      </CardTitle>
    </CardHeader>
    <CardContent>
      <div class="text-3xl font-semibold">{{ value.toFixed(1) }}{{ unit }}</div>
    </CardContent>
  </Card>
</template>
