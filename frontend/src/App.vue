<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Activity, Wrench } from 'lucide-vue-next'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui'
import Login from '@/components/Login.vue'
import MachineStatusBar from '@/components/hmi/MachineStatusBar.vue'
import DiagnosticsView from '@/views/DiagnosticsView.vue'
import OperationsView from '@/views/OperationsView.vue'
import { api, ApiError } from '@/api/client'
import { useSystemStatus } from '@/composables/useSystemStatus'
import { useTelemetry } from '@/composables/useTelemetry'
import { useAuthStore } from '@/stores/auth'
import type { CommandCapability } from '@/api/types'

const auth = useAuthStore()
const tab = ref('control')
const authenticated = computed(() => auth.user !== null)
const capabilities = ref<CommandCapability[]>([])
const handleUnauthorized = () => auth.clearSession()

const { data, error: telemetryError } = useTelemetry(authenticated, handleUnauthorized)
const { systemStatus, statusState, error: statusError } = useSystemStatus(authenticated, handleUnauthorized)
const operationalWarning = computed(() => statusError.value || telemetryError.value)

watch(authenticated, async (enabled) => {
  capabilities.value = []
  if (!enabled) return
  try {
    capabilities.value = (await api.getCommandCapabilities()).capabilities
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 401) handleUnauthorized()
  }
}, { immediate: true })

onMounted(() => auth.initializeSession())
</script>

<template>
  <div v-if="!auth.initialized" class="grid min-h-screen place-items-center bg-slate-100 text-sm text-slate-500">
    Establishing backend session…
  </div>

  <Login v-else-if="!auth.user" />

  <div v-else class="min-h-screen bg-slate-100 text-slate-900">
    <MachineStatusBar id="machine-status" :user="auth.user" :status="systemStatus" :status-state="statusState" @logout="auth.logout" />

    <Tabs v-model="tab">
      <div class="sticky top-14 z-30 border-b bg-white/95 px-4 py-2 backdrop-blur">
        <div class="mx-auto flex max-w-[1920px] items-center justify-between">
          <TabsList class="h-9 rounded bg-slate-100 p-1">
            <TabsTrigger value="control" class="h-7 gap-2 px-4 text-xs"><Activity class="size-4" /> Control</TabsTrigger>
            <TabsTrigger value="diagnostics" class="h-7 gap-2 px-4 text-xs"><Wrench class="size-4" /> Diagnostics</TabsTrigger>
          </TabsList>
          <div class="text-[10px] uppercase tracking-[0.16em] text-slate-400">Backend-authoritative monitoring · writes disabled</div>
        </div>
      </div>

      <main class="mx-auto max-w-[1920px] p-3">
        <div v-if="operationalWarning" class="mb-3 border-l-4 border-amber-500 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-900">
          {{ operationalWarning }}
        </div>

        <TabsContent value="control" class="mt-0">
          <OperationsView
            :status="systemStatus"
            :capabilities="capabilities"
            :active="tab === 'control'"
            @diagnostics="tab = 'diagnostics'"
          />
        </TabsContent>

        <TabsContent value="diagnostics" class="mt-0">
          <DiagnosticsView
            :status="systemStatus"
            :status-state="statusState"
            :capabilities="capabilities"
            :data="data"
            :active="tab === 'diagnostics'"
            :role="auth.user.role"
          />
        </TabsContent>
      </main>
    </Tabs>
  </div>
</template>
