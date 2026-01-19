<script setup lang="ts">
import { ref } from 'vue'
import { Button, Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui'
import StatusDot from '@/components/StatusDot.vue'
import Login from '@/components/Login.vue'
import DashboardView from '@/views/DashboardView.vue'
import PowerView from '@/views/PowerView.vue'
import MonitoringView from '@/views/MonitoringView.vue'
import PowerFlowView from '@/views/PowerFlowView.vue'
import SafetyView from '@/views/SafetyView.vue'
import StartupWizardView from '@/views/StartupWizardView.vue'
import LogsView from '@/views/LogsView.vue'
import AdminView from '@/views/AdminView.vue'
import { useTelemetry } from '@/composables/useTelemetry'

// Auth state
const user = ref<{ username: string, role: string } | null>(() => {
  const u = localStorage.getItem("gyro_user")
  const r = localStorage.getItem("gyro_role")
  if (u && r) return { username: u, role: r }
  return null
})

const tab = ref("dashboard")
const cpsOn = ref(true)
const apsOn = ref(false)
const faults = ref<string[]>([])
const { data, latest } = useTelemetry()

function handleLogin(username: string, role: string) {
  localStorage.setItem("gyro_user", username)
  localStorage.setItem("gyro_role", role)
  user.value = { username, role }
}

function handleLogout() {
  localStorage.removeItem("gyro_user")
  localStorage.removeItem("gyro_role")
  user.value = null
}

function goTo(tabName: string, id?: string) {
  tab.value = tabName
  if (id) {
    setTimeout(() => {
      const el = document.getElementById(id)
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" })
        el.classList.add("ring", "ring-amber-400", "rounded-xl")
        setTimeout(() => el.classList.remove("ring", "ring-amber-400", "rounded-xl"), 1500)
      }
    }, 50)
  }
}
</script>

<template>
  <div v-if="!user" class="min-h-screen bg-slate-50">
     <Login @login="handleLogin" />
  </div>

  <div v-else class="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 text-slate-900">
    <header class="sticky top-0 z-30 backdrop-blur bg-white/70 border-b">
      <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="size-8 rounded-xl bg-slate-900 text-white grid place-items-center">GT</div>
          <div>
            <div class="font-semibold">Gyrotron Power Control <span class="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded-full ml-2">Vue Edition</span></div>
            <div class="text-xs text-muted-foreground">ADAM-5000E • CPS / APS / Interlocks</div>
          </div>
        </div>
        <div class="flex items-center gap-4">
          <div class="flex items-center gap-2">
            <StatusDot :ok="faults.length === 0" />
            <span class="text-sm">{{ faults.length === 0 ? "Nominal" : "Fault" }}</span>
          </div>
          <div class="flex items-center gap-2 border-l pl-4">
            <span class="text-sm font-medium text-slate-600">{{ user.username }} <span class="text-xs text-muted-foreground">({{ user.role }})</span></span>
            <Button v-if="user.role === 'admin'" variant="ghost" size="sm" @click="tab = 'admin'" class="h-8 text-xs text-muted-foreground hover:text-blue-600 mr-1">
              Admin
            </Button>
            <Button variant="ghost" size="sm" @click="handleLogout" class="h-8 text-xs text-muted-foreground hover:text-red-600">
              Sign out
            </Button>
          </div>
        </div>
      </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 py-6">
      <Tabs v-model="tab">
        <TabsList class="rounded-2xl">
          <TabsTrigger value="dashboard">Dashboard</TabsTrigger>
          <TabsTrigger value="power">Power</TabsTrigger>
          <TabsTrigger value="monitoring">Monitoring</TabsTrigger>
          <TabsTrigger value="flow">Power Flow</TabsTrigger>
          <TabsTrigger value="safety">Safety</TabsTrigger>
          <TabsTrigger value="startup">Startup</TabsTrigger>
          <TabsTrigger value="logs">Logs</TabsTrigger>
          <!-- Admin tab trigger hidden, accessed via header button, but content needs to be here if we want to switch to it via v-model -->
          <TabsTrigger value="admin" class="hidden">Admin</TabsTrigger> 
        </TabsList>
        <div class="mt-6" />
        <TabsContent value="dashboard"><DashboardView :cpsOn="cpsOn" :apsOn="apsOn" :faults="faults" :data="data" :latest="latest" /></TabsContent>
        <TabsContent value="power"><PowerView /></TabsContent>
        <TabsContent value="monitoring"><MonitoringView :data="data" :latest="latest" /></TabsContent>
        <TabsContent value="flow"><PowerFlowView /></TabsContent>
        <TabsContent value="safety"><SafetyView /></TabsContent>
        <TabsContent value="startup"><StartupWizardView :goTo="goTo" /></TabsContent>
        <TabsContent value="logs"><LogsView /></TabsContent>
        <TabsContent value="admin"><AdminView /></TabsContent>
      </Tabs>
    </main>
  </div>
</template>
