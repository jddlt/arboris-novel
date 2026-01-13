<script setup lang="ts">
import { computed, watch } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import { NMessageProvider } from 'naive-ui'
import CustomAlert from '@/components/CustomAlert.vue'
import GMAgentPanelWS from '@/components/GMAgentPanelWS.vue'
import { globalAlert } from '@/composables/useAlert'
import { useGMPanelStore } from '@/stores/gmPanel'
import { useNovelStore } from '@/stores/novel'

const route = useRoute()
const gmPanelStore = useGMPanelStore()
const novelStore = useNovelStore()

// 从路由参数中获取项目 ID（支持 /detail/:id 和 /novel/:id）
const currentProjectId = computed(() => {
  const id = route.params.id
  return typeof id === 'string' ? id : null
})

// 判断当前路由是否是项目相关页面（非管理员）
const isProjectRoute = computed(() => {
  const name = route.name as string | undefined
  return name === 'novel-detail' || name === 'writing-desk'
})

// 当路由变化时，更新 store 中的 activeProjectId
watch(currentProjectId, (newId) => {
  if (newId && isProjectRoute.value) {
    gmPanelStore.setActiveProject(newId)
  }
}, { immediate: true })

// 面板是否显示
const showGMAgentPanel = computed(() => {
  return isProjectRoute.value && gmPanelStore.isPanelOpen
})

// 刷新当前项目数据
async function handleRefresh() {
  console.log('[App] handleRefresh called, projectId:', currentProjectId.value)
  if (currentProjectId.value) {
    await novelStore.loadProject(currentProjectId.value, true)
    console.log('[App] loadProject completed')
  }
}
</script>

<template>
  <n-message-provider>
    <div>
      <RouterView />

      <!-- 全局 AI 助手面板 -->
      <aside
        v-if="isProjectRoute && currentProjectId"
        class="fixed right-0 top-0 bottom-0 z-30 w-[450px] min-[1600px]:w-[520px] bg-white border-l border-slate-200/60 transform transition-transform duration-300 ease-out"
        :class="showGMAgentPanel ? 'translate-x-0' : 'translate-x-full'"
      >
        <!-- 使用 v-show 保持组件挂载，避免请求中断 -->
        <GMAgentPanelWS
          v-show="showGMAgentPanel"
          :project-id="currentProjectId"
          @close="gmPanelStore.closePanel()"
          @refresh="handleRefresh"
        />
      </aside>

      <!-- 全局提示框 -->
      <CustomAlert
        v-for="alert in globalAlert.alerts.value"
        :key="alert.id"
        :visible="alert.visible"
        :type="alert.type"
        :title="alert.title"
        :message="alert.message"
        :show-cancel="alert.showCancel"
        :confirm-text="alert.confirmText"
        :cancel-text="alert.cancelText"
        @confirm="globalAlert.closeAlert(alert.id, true)"
        @cancel="globalAlert.closeAlert(alert.id, false)"
        @close="globalAlert.closeAlert(alert.id, false)"
      />
    </div>
  </n-message-provider>
</template>

<style scoped>
</style>
