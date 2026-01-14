<template>
  <div class="gm-agent-panel relative flex flex-col h-full bg-gray-50">
    <!-- 头部 -->
    <div class="flex-shrink-0 h-16 px-4 bg-white border-b border-gray-200 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
          <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
          </svg>
        </div>
        <div>
          <h2 class="font-semibold text-gray-800">剧本大师 GM</h2>
          <div class="flex items-center gap-2 text-xs">
            <span
              class="flex items-center gap-1"
              :class="isConnected ? 'text-green-600' : 'text-gray-400'"
            >
              <span class="w-2 h-2 rounded-full" :class="isConnected ? 'bg-green-500' : 'bg-gray-400'"></span>
              {{ connectionStatusText }}
            </span>
          </div>
        </div>
      </div>

      <div class="flex items-center gap-1">
        <!-- 历史对话按钮 -->
        <button
          @click="toggleHistoryPanel"
          class="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          :class="showHistoryPanel ? 'bg-gray-100' : ''"
          title="历史对话"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
        </button>
        <!-- 新建对话按钮 -->
        <button
          @click="startNewConversation"
          class="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          title="新建对话"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
          </svg>
        </button>
        <!-- 关闭按钮 -->
        <button
          @click="$emit('close')"
          class="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          title="关闭"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>

    <!-- 历史对话浮层 -->
    <Transition
      enter-active-class="transition-all duration-200 ease-out"
      leave-active-class="transition-all duration-150 ease-in"
      enter-from-class="opacity-0 scale-95"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="showHistoryPanel"
        class="absolute top-16 right-4 left-4 z-20 bg-white rounded-xl shadow-xl border border-gray-200 max-h-80 overflow-hidden flex flex-col"
      >
        <!-- 浮层头部 -->
        <div class="flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-gray-50">
          <span class="text-sm font-medium text-gray-700">历史对话</span>
          <button
            @click="showHistoryPanel = false"
            class="p-1 text-gray-400 hover:text-gray-600 rounded"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- 加载中 -->
        <div v-if="isLoadingHistory" class="flex items-center justify-center py-8">
          <div class="w-5 h-5 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
          <span class="ml-2 text-sm text-gray-500">加载中...</span>
        </div>

        <!-- 无历史记录 -->
        <div v-else-if="historyList.length === 0" class="py-8 text-center text-gray-500 text-sm">
          暂无历史对话
        </div>

        <!-- 历史列表 -->
        <div v-else class="flex-1 overflow-y-auto divide-y divide-gray-100">
          <div
            v-for="conv in historyList"
            :key="conv.id"
            class="flex items-center px-4 py-3 hover:bg-gray-50 transition-colors group"
            :class="conversationId === conv.id ? 'bg-indigo-50' : ''"
          >
            <button
              @click="selectConversation(conv)"
              class="flex-1 text-left min-w-0"
            >
              <div class="text-sm font-medium text-gray-900 truncate">{{ conv.title }}</div>
              <div class="flex items-center gap-2 text-xs text-gray-500 mt-0.5">
                <span>{{ conv.message_count }} 条消息</span>
                <span>·</span>
                <span>{{ formatTime(conv.updated_at) }}</span>
              </div>
            </button>
            <div class="flex items-center gap-2 flex-shrink-0 ml-2">
              <span
                v-if="conversationId === conv.id"
                class="px-1.5 py-0.5 rounded text-xs bg-indigo-100 text-indigo-700"
              >
                当前
              </span>
              <button
                @click.stop="deleteConversation(conv.id)"
                class="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded opacity-0 group-hover:opacity-100 transition-all"
                title="删除对话"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 点击外部关闭浮层 -->
    <div
      v-if="showHistoryPanel"
      class="fixed inset-0 z-10"
      @click="showHistoryPanel = false"
    ></div>

    <!-- 错误提示 -->
    <div v-if="lastError" class="flex-shrink-0 px-4 py-2 bg-red-50 border-b border-red-100">
      <div class="flex items-center gap-2 text-sm text-red-600">
        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
        </svg>
        {{ lastError }}
        <button @click="reconnect" class="ml-auto text-red-700 hover:underline">重新连接</button>
      </div>
    </div>

    <!-- 消息列表 -->
    <div ref="messageContainer" class="flex-1 overflow-auto p-4 space-y-4">
      <!-- 欢迎消息 -->
      <div v-if="messages.length === 0 && !isLoading" class="text-center text-gray-500 py-8">
        <div class="w-20 h-20 mx-auto mb-4 rounded-full bg-gradient-to-br from-indigo-100 to-purple-100 flex items-center justify-center">
          <svg class="w-10 h-10 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
        </div>
        <p class="text-xl font-medium text-gray-700 mb-2">你好！我是剧本大师GM</p>
        <p class="text-base text-gray-500 mb-4">你的全能小说创作助手</p>
        <div class="inline-flex flex-col items-start space-y-2 text-sm text-gray-400">
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 bg-indigo-400 rounded-full flex-shrink-0"></span>
            <span>角色、关系、世界观管理</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 bg-purple-400 rounded-full flex-shrink-0"></span>
            <span>章节大纲规划与卷分配</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 bg-pink-400 rounded-full flex-shrink-0"></span>
            <span>直接撰写或修改章节内容</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 bg-amber-400 rounded-full flex-shrink-0"></span>
            <span>创意灵感与剧情建议</span>
          </div>
        </div>
      </div>

      <!-- 消息 -->
      <template v-for="(msg, index) in messages" :key="index">
        <!-- 用户消息 -->
        <div v-if="msg.role === 'user'" class="flex justify-end items-center gap-2">
          <!-- 重发按钮（孤单消息时显示） -->
          <button
            v-if="isOrphanUserMessage(index)"
            @click="resendMessage(index)"
            :disabled="!isConnected || isLoading"
            class="flex-shrink-0 p-1.5 text-gray-400 hover:text-indigo-600 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="重新发送"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
          <div class="max-w-[80%] bg-indigo-600 text-white px-4 py-2 rounded-2xl rounded-tr-sm">
            <!-- 图片预览 -->
            <div v-if="msg.images && msg.images.length > 0" class="flex flex-wrap gap-1 mb-2">
              <img
                v-for="(img, imgIdx) in msg.images"
                :key="imgIdx"
                :src="`data:${img.mime_type};base64,${img.base64}`"
                class="w-20 h-20 object-cover rounded-lg"
              />
            </div>
            <span v-if="msg.content">{{ msg.content }}</span>
          </div>
        </div>

        <!-- AI 消息 -->
        <div v-else class="flex justify-start group/msg">
          <div class="max-w-[85%]">
            <!-- 工具执行记录（过滤掉系统工具） -->
            <div v-if="getVisibleTools(msg.tools).length > 0" class="mb-2">
              <button
                @click="toggleToolsExpanded(index)"
                class="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 transition-colors"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                执行了 {{ getVisibleTools(msg.tools).length }} 个工具
                <!-- 成功/失败统计 -->
                <span v-if="getToolStats(msg.tools).success > 0" class="flex items-center gap-0.5 text-green-600">
                  <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                  </svg>
                  {{ getToolStats(msg.tools).success }}
                </span>
                <span v-if="getToolStats(msg.tools).failed > 0" class="flex items-center gap-0.5 text-red-600">
                  <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
                  </svg>
                  {{ getToolStats(msg.tools).failed }}
                </span>
                <svg
                  class="w-4 h-4 transition-transform"
                  :class="{ 'rotate-180': expandedTools.has(index) }"
                  fill="none" stroke="currentColor" viewBox="0 0 24 24"
                >
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              <div v-if="expandedTools.has(index)" class="mt-2 space-y-1">
                <div
                  v-for="(tool, ti) in getVisibleTools(msg.tools)"
                  :key="ti"
                  class="text-xs px-3 py-2 bg-gray-100 rounded-lg flex items-center gap-2"
                >
                  <span
                    class="w-2 h-2 rounded-full"
                    :class="{
                      'bg-green-500': tool.status === 'applied' || tool.status === 'success',
                      'bg-red-500': tool.status === 'failed',
                      'bg-yellow-500 animate-pulse': tool.status === 'executing',
                    }"
                  ></span>
                  <span class="font-medium">{{ getToolLabel(tool.tool_name) }}</span>
                  <span v-if="tool.message" class="text-gray-500 truncate">{{ tool.message }}</span>
                </div>
              </div>
            </div>

            <!-- 消息内容 -->
            <div class="bg-white px-4 py-3 rounded-2xl rounded-tl-sm shadow-sm border border-gray-100">
              <div
                class="prose prose-sm max-w-none"
                v-html="renderMarkdown(shouldTruncate(msg.content, index) ? truncateContent(msg.content) : msg.content)"
              ></div>
              <button
                v-if="isLongContent(msg.content) && !isLastMessage(index)"
                @click="showFullContent(msg.content)"
                class="mt-2 text-xs font-medium text-indigo-600 hover:text-indigo-800 underline"
              >
                查看全文（{{ msg.content.length }} 字）
              </button>

              <!-- 待确认操作（内联显示） -->
              <div v-if="msg.actions && msg.actions.length > 0" class="mt-3 space-y-2">
                <div
                  v-for="action in msg.actions"
                  :key="action.action_id"
                  class="bg-gray-50 rounded-lg p-2.5 border border-gray-200"
                >
                  <div class="flex items-start justify-between gap-2">
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-1.5">
                        <span class="text-xs font-medium text-indigo-600">{{ getToolLabel(action.tool_name) }}</span>
                        <!-- 展开/收起按钮 -->
                        <button
                          v-if="action.params && Object.keys(action.params).length > 0"
                          @click="toggleActionDetails(action.action_id)"
                          class="p-0.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
                          :title="expandedActions.has(action.action_id) ? '收起详情' : '展开详情'"
                        >
                          <svg
                            class="w-3 h-3 transition-transform"
                            :class="{ 'rotate-180': expandedActions.has(action.action_id) }"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                          </svg>
                        </button>
                      </div>
                      <p class="text-xs text-gray-600 mt-0.5 truncate">{{ action.preview }}</p>
                    </div>
                    <!-- pending 状态显示确认/拒绝按钮 -->
                    <div v-if="action.status === 'pending'" class="flex gap-1 flex-shrink-0">
                      <button
                        @click="approveAction(action.id)"
                        :disabled="isApplying"
                        class="p-1 text-green-600 hover:bg-green-50 rounded transition-colors disabled:opacity-50"
                        title="应用"
                      >
                        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
                        </svg>
                      </button>
                      <button
                        @click="rejectAction(action.id)"
                        :disabled="isApplying"
                        class="p-1 text-red-600 hover:bg-red-50 rounded transition-colors disabled:opacity-50"
                        title="放弃"
                      >
                        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
                        </svg>
                      </button>
                    </div>
                    <!-- 非 pending 状态显示状态标签 -->
                    <span v-else :class="getStatusClass(action.status)" class="text-xs px-1.5 py-0.5 rounded flex-shrink-0">
                      {{ getStatusLabel(action.status) }}
                    </span>
                  </div>
                  <!-- 展开的参数详情 -->
                  <Transition
                    enter-active-class="transition-all duration-200 ease-out"
                    leave-active-class="transition-all duration-150 ease-in"
                    enter-from-class="opacity-0 max-h-0"
                    leave-to-class="opacity-0 max-h-0"
                    enter-to-class="opacity-100 max-h-96"
                    leave-from-class="opacity-100 max-h-96"
                  >
                    <div
                      v-if="expandedActions.has(action.action_id) && action.params && Object.keys(action.params).length > 0"
                      class="mt-2 pt-2 border-t border-gray-100 space-y-1 overflow-hidden"
                    >
                      <div
                        v-for="(value, key) in action.params"
                        :key="key"
                        class="text-xs"
                      >
                        <span class="text-gray-500">{{ key }}:</span>
                        <span class="ml-1 text-gray-700 whitespace-pre-wrap break-all">{{ formatParamValue(value) }}</span>
                      </div>
                    </div>
                  </Transition>
                </div>
                <!-- 批量操作按钮（历史消息，仅当有未处理的操作时显示） -->
                <div
                  v-if="msg.actions.some(a => a.status === 'pending' || a.status === 'approved' || a.status === 'rejected') && msg.actions.some(a => a.status !== 'applied' && a.status !== 'failed')"
                  class="flex justify-end gap-2 pt-2 border-t border-gray-100"
                >
                  <button
                    v-if="msg.actions.filter(a => a.status === 'pending').length > 1"
                    @click="confirmAll(msg.actions)"
                    :disabled="isApplying"
                    class="px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition-colors disabled:opacity-50"
                  >
                    全选
                  </button>
                  <button
                    v-if="msg.actions.filter(a => a.status === 'pending').length > 1"
                    @click="rejectAll(msg.actions)"
                    :disabled="isApplying"
                    class="px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition-colors disabled:opacity-50"
                  >
                    全不选
                  </button>
                  <button
                    v-if="msg.actions.some(a => a.status !== 'applied' && a.status !== 'failed')"
                    @click="submitHistoryActions(msg.actions)"
                    :disabled="isApplying"
                    class="px-3 py-1 text-xs text-white rounded transition-colors disabled:opacity-50"
                    :class="msg.actions.filter(a => a.status === 'approved').length > 0 ? 'bg-indigo-500 hover:bg-indigo-600' : 'bg-gray-500 hover:bg-gray-600'"
                  >
                    <template v-if="msg.actions.filter(a => a.status === 'approved').length > 0">
                      确认选择 ({{ msg.actions.filter(a => a.status === 'approved').length }})
                    </template>
                    <template v-else>
                      全部放弃
                    </template>
                  </button>
                </div>
              </div>
            </div>

            <!-- 回溯按钮（hover 时显示） -->
            <div
              v-if="canRevertToMessage(index)"
              class="mt-1 opacity-0 group-hover/msg:opacity-100 transition-opacity duration-200"
            >
              <button
                @click="revertToMessage(index)"
                :disabled="isReverting"
                class="flex items-center gap-1 px-2 py-1 text-xs text-gray-400 hover:text-orange-600 hover:bg-orange-50 rounded transition-colors disabled:opacity-50"
                title="回溯到此处，删除后续对话"
              >
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
                </svg>
                回溯到此处
              </button>
            </div>
          </div>
        </div>
      </template>

      <!-- 流式内容 -->
      <div v-if="streamingContent || isLoading || pendingConfirm" class="flex justify-start">
        <div class="max-w-[85%]">
          <!-- 执行中的工具汇总（只显示一行） -->
          <div v-if="visibleExecutingTools.length > 0" class="mb-2">
            <div class="text-xs px-3 py-2 bg-indigo-50 rounded-lg flex items-center gap-2">
              <span class="w-2 h-2 rounded-full bg-indigo-500 animate-pulse"></span>
              <span class="text-indigo-700">正在调用 {{ visibleExecutingTools.length }} 个工具...</span>
            </div>
          </div>

          <!-- 流式文本 -->
          <div v-if="streamingContent" class="bg-white px-4 py-3 rounded-2xl rounded-tl-sm shadow-sm border border-gray-100">
            <div class="prose prose-sm max-w-none" v-html="renderMarkdown(streamingContent)"></div>
            <span class="inline-block w-2 h-4 bg-indigo-500 animate-pulse ml-1"></span>
          </div>

          <!-- 待确认操作卡片 -->
          <div v-if="pendingConfirm && pendingConfirm.actions.length > 0" class="mt-3 space-y-2">
            <div class="text-sm font-medium text-gray-700 mb-2">待确认操作：</div>
            <div
              v-for="action in pendingConfirm.actions"
              :key="action.action_id"
              class="bg-gray-50 rounded-lg p-2.5 border border-gray-200"
            >
              <div class="flex items-start justify-between gap-2">
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-1.5">
                    <span class="text-xs font-medium text-indigo-600">{{ getToolLabel(action.tool_name) }}</span>
                    <!-- 展开/收起按钮 -->
                    <button
                      v-if="action.params && Object.keys(action.params).length > 0"
                      @click="toggleActionDetails(action.action_id)"
                      class="p-0.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
                      :title="expandedActions.has(action.action_id) ? '收起详情' : '展开详情'"
                    >
                      <svg
                        class="w-3 h-3 transition-transform"
                        :class="{ 'rotate-180': expandedActions.has(action.action_id) }"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                      </svg>
                    </button>
                  </div>
                  <p class="text-xs text-gray-600 mt-0.5 truncate">{{ action.preview }}</p>
                </div>
                <!-- pending 状态显示确认/拒绝按钮 -->
                <div v-if="action.status === 'pending'" class="flex gap-1 flex-shrink-0">
                  <button
                    @click="approveAction(action.id)"
                    :disabled="isApplying"
                    class="p-1 text-green-600 hover:bg-green-50 rounded transition-colors disabled:opacity-50"
                    title="应用"
                  >
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
                    </svg>
                  </button>
                  <button
                    @click="rejectAction(action.id)"
                    :disabled="isApplying"
                    class="p-1 text-red-600 hover:bg-red-50 rounded transition-colors disabled:opacity-50"
                    title="放弃"
                  >
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
                    </svg>
                  </button>
                </div>
                <!-- 非 pending 状态显示状态标签 -->
                <span v-else :class="getStatusClass(action.status)" class="text-xs px-1.5 py-0.5 rounded flex-shrink-0">
                  {{ getStatusLabel(action.status) }}
                </span>
              </div>
              <!-- 展开的参数详情 -->
              <Transition
                enter-active-class="transition-all duration-200 ease-out"
                leave-active-class="transition-all duration-150 ease-in"
                enter-from-class="opacity-0 max-h-0"
                leave-to-class="opacity-0 max-h-0"
                enter-to-class="opacity-100 max-h-96"
                leave-from-class="opacity-100 max-h-96"
              >
                <div
                  v-if="expandedActions.has(action.action_id) && action.params && Object.keys(action.params).length > 0"
                  class="mt-2 pt-2 border-t border-gray-100 space-y-1 max-h-64 overflow-y-auto"
                >
                  <div
                    v-for="(value, key) in action.params"
                    :key="key"
                    class="text-xs"
                  >
                    <span class="text-gray-500">{{ key }}:</span>
                    <span class="ml-1 text-gray-700 whitespace-pre-wrap break-all">{{ formatParamValue(value) }}</span>
                  </div>
                </div>
              </Transition>
            </div>
            <!-- 批量操作按钮 -->
            <div class="flex justify-end gap-2 pt-2 border-t border-gray-100">
              <button
                v-if="pendingConfirm.actions.filter(a => a.status === 'pending').length > 1"
                @click="confirmAllPending"
                :disabled="isApplying"
                class="px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition-colors disabled:opacity-50"
              >
                全选
              </button>
              <button
                v-if="pendingConfirm.actions.filter(a => a.status === 'pending').length > 1"
                @click="rejectAllPending"
                :disabled="isApplying"
                class="px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition-colors disabled:opacity-50"
              >
                全不选
              </button>
              <button
                @click="submitPendingActions"
                :disabled="isApplying"
                class="px-3 py-1 text-xs text-white rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                :class="pendingConfirm.actions.filter(a => a.status === 'approved').length > 0 ? 'bg-indigo-500 hover:bg-indigo-600' : 'bg-gray-500 hover:bg-gray-600'"
              >
                <template v-if="pendingConfirm.actions.filter(a => a.status === 'approved').length > 0">
                  确认选择 ({{ pendingConfirm.actions.filter(a => a.status === 'approved').length }})
                </template>
                <template v-else>
                  全部放弃
                </template>
              </button>
            </div>
          </div>

          <!-- 加载指示器 -->
          <div v-else-if="isLoading" class="bg-white px-4 py-3 rounded-2xl rounded-tl-sm shadow-sm border border-gray-100">
            <div class="flex items-center gap-2 text-gray-500">
              <div class="flex space-x-1">
                <div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0ms"></div>
                <div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 150ms"></div>
                <div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 300ms"></div>
              </div>
              <span class="text-sm">思考中...</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="flex-shrink-0 p-4 bg-white border-t border-gray-200">
      <!-- 已粘贴的图片预览 -->
      <div v-if="pastedImages.length > 0" class="mb-2 flex flex-wrap gap-2">
        <div
          v-for="(img, index) in pastedImages"
          :key="index"
          class="relative group"
        >
          <img
            :src="`data:${img.mime_type};base64,${img.base64}`"
            class="w-16 h-16 object-cover rounded-lg border border-gray-200"
          />
          <button
            @click="removeImage(index)"
            class="absolute -top-1.5 -right-1.5 w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
      <div class="flex gap-2 items-start">
        <textarea
          ref="inputRef"
          v-model="inputMessage"
          @keydown.enter.exact.prevent="sendMessage"
          @paste="handlePaste"
          :disabled="!isConnected"
          placeholder="输入消息...（可粘贴图片）"
          rows="4"
          class="flex-1 px-3 py-2 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent disabled:bg-gray-100 text-sm"
        ></textarea>
        <div class="flex flex-col items-center gap-2">
          <button
            @click="sendMessage"
            :disabled="!isConnected || isLoading || (!inputMessage.trim() && pastedImages.length === 0)"
            class="px-4 py-3 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <svg v-if="isLoading" class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <svg v-else class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z"/>
            </svg>
          </button>
          <!-- 联网搜索开关 -->
          <label class="flex items-center gap-1 cursor-pointer" title="启用联网搜索（仅 Gemini 模型支持）">
            <input
              type="checkbox"
              v-model="enableWebSearch"
              class="w-3.5 h-3.5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
            <span class="text-xs text-gray-500">联网</span>
          </label>
        </div>
      </div>
    </div>

    <!-- 全文查看弹窗 -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition-all duration-200 ease-out"
        leave-active-class="transition-all duration-150 ease-in"
        enter-from-class="opacity-0"
        leave-to-class="opacity-0"
      >
        <div
          v-if="fullContentModal.show"
          class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
          @click.self="closeFullContent"
        >
          <div class="bg-white rounded-xl shadow-2xl max-w-3xl w-full max-h-[80vh] flex flex-col">
            <!-- 弹窗头部 -->
            <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200">
              <h3 class="text-lg font-semibold text-gray-800">完整内容</h3>
              <button
                @click="closeFullContent"
                class="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <!-- 弹窗内容 -->
            <div class="flex-1 overflow-auto px-6 py-4">
              <div
                class="prose prose-sm max-w-none"
                v-html="renderMarkdown(fullContentModal.content)"
              ></div>
            </div>
            <!-- 弹窗底部 -->
            <div class="flex justify-end px-6 py-4 border-t border-gray-200">
              <button
                @click="closeFullContent"
                class="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg transition-colors text-sm font-medium"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { marked } from 'marked'
import { useGMWebSocket } from '@/composables/useGMWebSocket'
import { getConversations, getConversationDetail, archiveConversation, applyActions, discardActions, truncateConversation } from '@/api/gm'
import type { ConversationSummary } from '@/api/gm'

// ==================== Props & Emits ====================

const props = defineProps<{
  projectId: string
}>()

const emit = defineEmits<{
  close: []
  refresh: []
}>()

// ==================== Composable ====================

const {
  connectionStatus,
  isConnected,
  lastError,
  conversationId,
  messages,
  isLoading,
  streamingContent,
  executingTools,
  executionStats,
  pendingConfirm,
  connect,
  reconnect,
  sendUserMessage,
  sendConfirmResponse,
  approveAction: wsApproveAction,
  rejectAction: wsRejectAction,
  confirmAll: wsConfirmAll,
  rejectAll: wsRejectAll,
  cancelTask,
  clearConversation: clearWsConversation,
  loadMessages,
  clearPendingConfirm,
  markActionsApplied,
  markActionsFailed,
} = useGMWebSocket(props.projectId)

// ==================== 状态 ====================

// localStorage key
const INPUT_STORAGE_KEY = `gm-input-${props.projectId}`

const inputMessage = ref(localStorage.getItem(INPUT_STORAGE_KEY) || '')
const inputRef = ref<HTMLTextAreaElement | null>(null)
const messageContainer = ref<HTMLDivElement | null>(null)
const expandedTools = ref(new Set<number>())

// 历史对话状态
const showHistoryPanel = ref(false)
const historyList = ref<ConversationSummary[]>([])
const isLoadingHistory = ref(false)

// 联网搜索
const enableWebSearch = ref(false)

// 粘贴图片
const pastedImages = ref<{ base64: string; mime_type: string }[]>([])

// 长内容截断相关
const LONG_CONTENT_THRESHOLD = 500
const fullContentModal = ref<{ show: boolean; content: string }>({ show: false, content: '' })

// 操作详情展开状态
const expandedActions = ref<Set<string>>(new Set())

// 回溯状态
const isReverting = ref(false)

// ==================== 计算属性 ====================

const connectionStatusText = computed(() => {
  switch (connectionStatus.value) {
    case 'connected': return '已连接'
    case 'connecting': return '连接中...'
    case 'error': return '连接错误'
    default: return '未连接'
  }
})

// 过滤掉系统工具的执行中工具列表
const visibleExecutingTools = computed(() => {
  return executingTools.value.filter(t => !HIDDEN_TOOLS.includes(t.tool_name))
})

// ==================== 方法 ====================

function sendMessage() {
  const message = inputMessage.value.trim()
  if ((!message && pastedImages.value.length === 0) || !isConnected.value || isLoading.value) return

  sendUserMessage(message, {
    enableWebSearch: enableWebSearch.value,
    images: pastedImages.value.length > 0 ? [...pastedImages.value] : undefined,
  })
  inputMessage.value = ''
  pastedImages.value = []
  localStorage.removeItem(INPUT_STORAGE_KEY)

  // 滚动到底部
  nextTick(() => {
    scrollToBottom()
  })
}

// 处理粘贴事件
async function handlePaste(event: ClipboardEvent) {
  const items = event.clipboardData?.items
  if (!items) return

  for (const item of items) {
    if (item.type.startsWith('image/')) {
      event.preventDefault()
      const file = item.getAsFile()
      if (!file) continue

      // 转换为 base64
      const base64 = await fileToBase64(file)
      pastedImages.value.push({
        base64,
        mime_type: item.type,
      })
    }
  }
}

// 文件转 base64
function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result as string
      // 去掉 data:image/xxx;base64, 前缀
      const base64 = result.split(',')[1]
      resolve(base64)
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

// 移除图片
function removeImage(index: number) {
  pastedImages.value.splice(index, 1)
}

function clearConversation() {
  clearWsConversation()
  expandedTools.value.clear()
}

// 是否正在应用操作
const isApplying = ref(false)

// 标记单个操作为 approved（只更新本地状态）
function approveAction(actionId: string) {
  wsApproveAction(actionId)
}

// 标记单个操作为 rejected（只更新本地状态）
function rejectAction(actionId: string) {
  wsRejectAction(actionId)
}

// 标记所有为 approved（用于流式区域的按钮，只更新本地状态）
function confirmAllPending() {
  wsConfirmAll()
}

// 标记所有为 rejected（用于流式区域的按钮，只更新本地状态）
function rejectAllPending() {
  wsRejectAll()
}

// 提交待确认操作（发送最终响应）
async function submitPendingActions() {
  if (!pendingConfirm.value) return

  const approvedIds = pendingConfirm.value.actions
    .filter(a => a.status === 'approved')
    .map(a => a.id)
  const rejectedIds = pendingConfirm.value.actions
    .filter(a => a.status === 'rejected')
    .map(a => a.id)

  // 如果还有未选择的，提示用户
  const pendingIds = pendingConfirm.value.actions
    .filter(a => a.status === 'pending')
    .map(a => a.id)

  if (pendingIds.length > 0) {
    // 未选择的默认拒绝
    rejectedIds.push(...pendingIds)
  }

  await applySelectedActions(approvedIds, rejectedIds)
}

// 标记所有为 approved（用于历史消息中的批量操作）
function confirmAll(actions?: Array<{ id: string; action_id?: string; status: string }>) {
  if (actions) {
    // 从传入的 actions 获取
    const pendingIds = actions.filter(a => a.status === 'pending').map(a => a.id)
    pendingIds.forEach(id => wsApproveAction(id))
  } else {
    wsConfirmAll()
  }
}

// 标记所有为 rejected（用于历史消息中的批量操作）
function rejectAll(actions?: Array<{ id: string; action_id?: string; status: string }>) {
  if (actions) {
    // 从传入的 actions 获取
    const pendingIds = actions.filter(a => a.status === 'pending').map(a => a.id)
    pendingIds.forEach(id => wsRejectAction(id))
  } else {
    wsRejectAll()
  }
}

// 提交历史消息中的操作（REST API）
async function submitHistoryActions(actions: Array<{ id: string; action_id?: string; status: string }>) {
  const approvedIds = actions.filter(a => a.status === 'approved').map(a => a.id)
  const rejectedIds = actions.filter(a => a.status === 'rejected').map(a => a.id)
  const pendingIds = actions.filter(a => a.status === 'pending').map(a => a.id)

  // 未选择的默认拒绝
  rejectedIds.push(...pendingIds)

  if (approvedIds.length === 0 && rejectedIds.length === 0) return

  isApplying.value = true
  try {
    if (approvedIds.length > 0) {
      const result = await applyActions(props.projectId, approvedIds)
      const successIds = result.results.filter(r => r.success).map(r => r.action_id)
      const failedIds = result.results.filter(r => !r.success).map(r => r.action_id)
      markActionsApplied(successIds)
      markActionsFailed(failedIds)
    }
    if (rejectedIds.length > 0) {
      await discardActions(props.projectId, rejectedIds)
    }
    emit('refresh')
  } catch (error) {
    console.error('应用操作失败:', error)
    markActionsFailed(approvedIds)
  } finally {
    isApplying.value = false
  }
}

// 执行选中的操作
async function applySelectedActions(approvedIds: string[], rejectedIds: string[] = []) {
  if (approvedIds.length === 0 && rejectedIds.length === 0) return
  isApplying.value = true
  try {
    // 如果是当前轮次需要 WebSocket 确认的操作，通过 WebSocket 发送
    if (pendingConfirm.value?.awaitingConfirmation) {
      // 通过 WebSocket 发送确认响应
      const sent = sendConfirmResponse(approvedIds, rejectedIds)
      if (sent) {
        // 清除 pendingConfirm（后端会继续执行并发送结果）
        clearPendingConfirm()
        // 刷新由 watch(executionStats) 在 done 消息到达时触发
      }
    } else {
      // 历史对话或刷新后的场景，使用 REST API 执行操作
      if (approvedIds.length > 0) {
        const result = await applyActions(props.projectId, approvedIds)
        // 根据结果更新状态
        const successIds = result.results.filter(r => r.success).map(r => r.action_id)
        const failedIds = result.results.filter(r => !r.success).map(r => r.action_id)

        markActionsApplied(successIds)
        markActionsFailed(failedIds)
      }

      // 处理拒绝的操作
      if (rejectedIds.length > 0) {
        await discardActions(props.projectId, rejectedIds)
      }

      // 如果所有操作都处理完了，清除 pendingConfirm
      if (pendingConfirm.value) {
        const stillPending = pendingConfirm.value.actions.filter(a => a.status === 'pending')
        if (stillPending.length === 0) {
          clearPendingConfirm()
        }
      }

      // 刷新数据
      emit('refresh')

      // ★ 历史操作确认后，自动让模型继续（如果有操作被批准）
      console.log('[GM] 检查是否自动继续:', {
        approvedCount: approvedIds.length,
        isConnected: isConnected.value,
        isLoading: isLoading.value
      })
      if (approvedIds.length > 0 && isConnected.value && !isLoading.value) {
        // 发送一条"继续"消息，让模型基于已执行的操作继续
        console.log('[GM] 发送"请继续"消息')
        sendUserMessage('请继续', { enableWebSearch: false })
      }
    }
  } catch (error) {
    console.error('应用操作失败:', error)
    markActionsFailed(approvedIds)
  } finally {
    isApplying.value = false
  }
}

// 新建对话（只清空本地状态，保留历史）
function startNewConversation() {
  clearWsConversation()
  expandedTools.value.clear()
  showHistoryPanel.value = false
}

// 加载历史对话列表
async function loadHistoryList() {
  if (isLoadingHistory.value) return
  isLoadingHistory.value = true
  try {
    historyList.value = await getConversations(props.projectId)
  } catch (error) {
    console.error('加载历史对话失败:', error)
  } finally {
    isLoadingHistory.value = false
  }
}

// 切换历史面板显示
async function toggleHistoryPanel() {
  showHistoryPanel.value = !showHistoryPanel.value
  if (showHistoryPanel.value) {
    await loadHistoryList()
  }
}

// 选择历史对话
async function selectConversation(conv: ConversationSummary) {
  try {
    isLoadingHistory.value = true
    const detail = await getConversationDetail(props.projectId, conv.id)
    // 转换消息格式并加载（过滤掉 tool 角色的消息，这些结果已在 actions 卡片中显示）
    const gmMessages = detail.messages
      .filter(msg => msg.role === 'user' || msg.role === 'assistant')
      .map(msg => {
      // 优先使用 executed_tools（WebSocket 模式），其次使用 actions（SSE 模式）
      let tools = undefined
      let actions = undefined

      if (msg.executed_tools && msg.executed_tools.length > 0) {
        // executed_tools 格式与前端 ToolExecution 一致
        tools = msg.executed_tools.map((t: { tool_name: string; params?: Record<string, unknown>; status: string; message?: string; preview?: string }) => ({
          tool_name: t.tool_name,
          params: t.params || {},
          status: t.status as 'executing' | 'success' | 'failed',
          message: t.message,
          preview: t.preview,
        }))
      }

      // 处理待确认操作（无论是否有 executed_tools，都可能有 actions）
      if (msg.actions && msg.actions.length > 0) {
        actions = msg.actions.map((a: { action_id: string; tool_name: string; params: Record<string, unknown>; status: string; preview?: string }) => ({
          id: a.action_id,
          action_id: a.action_id,
          tool_name: a.tool_name,
          params: a.params,
          preview: a.preview || '',
          is_dangerous: false,
          status: a.status as 'pending' | 'approved' | 'rejected' | 'applied' | 'failed',
        }))

        // 如果没有 executed_tools，将 actions 转换为 tools 显示
        if (!tools) {
          tools = msg.actions.map((a: { tool_name: string; params: Record<string, unknown>; status: string; preview?: string }) => ({
            tool_name: a.tool_name,
            params: a.params,
            status: a.status as 'executing' | 'success' | 'failed',
            preview: a.preview
          }))
        }
      }

      return {
        role: msg.role as 'user' | 'assistant',
        content: msg.content,
        tools,
        actions,
        timestamp: new Date(msg.timestamp || Date.now()).getTime()
      }
    })
    loadMessages(gmMessages, conv.id)
    showHistoryPanel.value = false
    expandedTools.value.clear()
  } catch (error) {
    console.error('加载对话详情失败:', error)
  } finally {
    isLoadingHistory.value = false
  }
}

// 格式化时间
function formatTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  if (diff < 604800000) return `${Math.floor(diff / 86400000)} 天前`

  return date.toLocaleDateString()
}

// 删除对话
async function deleteConversation(convId: string) {
  try {
    await archiveConversation(props.projectId, convId)
    // 从列表中移除
    historyList.value = historyList.value.filter(c => c.id !== convId)
    // 如果删除的是当前对话，清空
    if (conversationId.value === convId) {
      startNewConversation()
    }
  } catch (error) {
    console.error('删除对话失败:', error)
  }
}

function toggleToolsExpanded(index: number) {
  if (expandedTools.value.has(index)) {
    expandedTools.value.delete(index)
  } else {
    expandedTools.value.add(index)
  }
}

// 工具标签映射
const toolLabels: Record<string, string> = {
  update_blueprint: '修改设定',
  add_character: '添加角色',
  update_character: '修改角色',
  delete_character: '删除角色',
  add_relationship: '添加关系',
  update_relationship: '修改关系',
  delete_relationship: '删除关系',
  add_outline: '添加大纲',
  update_outline: '修改大纲',
  delete_outline: '删除大纲',
  reorder_outlines: '调整顺序',
  search_content: '搜索内容',
  get_chapter_content: '获取章节',
  get_chapter_versions: '获取版本',
  update_chapter_content: '修改章节',
  clear_chapter_content: '清空章节',
  generate_chapter_content: '生成章节',
  add_volume: '添加卷',
  update_volume: '修改卷',
  delete_volume: '删除卷',
  add_foreshadowing: '添加伏笔',
  update_foreshadowing: '修改伏笔',
  delete_foreshadowing: '删除伏笔',
  add_world_item: '添加世界设定',
  update_world_item: '修改世界设定',
  delete_world_item: '删除世界设定',
}

function getToolLabel(toolName: string): string {
  return toolLabels[toolName] || toolName
}

// 获取状态标签
function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: '待确认',
    approved: '已确认',
    rejected: '已拒绝',
    applied: '已应用',
    success: '已应用',
    failed: '失败',
    discarded: '已取消',
  }
  return labels[status] || status
}

// 获取状态样式
function getStatusClass(status: string): string {
  const classes: Record<string, string> = {
    pending: 'bg-amber-100 text-amber-700',
    approved: 'bg-blue-100 text-blue-700',
    rejected: 'bg-gray-100 text-gray-500',
    applied: 'bg-green-100 text-green-700',
    success: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-700',
    discarded: 'bg-gray-100 text-gray-500',
  }
  return classes[status] || 'bg-gray-100 text-gray-600'
}

// 切换操作详情展开状态
function toggleActionDetails(actionId: string) {
  if (expandedActions.value.has(actionId)) {
    expandedActions.value.delete(actionId)
  } else {
    expandedActions.value.add(actionId)
  }
}

// 格式化参数值
function formatParamValue(value: unknown): string {
  if (value === null || value === undefined) {
    return 'null'
  }
  if (typeof value === 'object') {
    const str = JSON.stringify(value, null, 2)
    // 展开后显示完整内容，不截断
    return str
  }
  return String(value)
}

// 隐藏系统工具列表
const HIDDEN_TOOLS = ['signal_task_status']

// 获取可见工具（过滤掉系统工具）
function getVisibleTools(tools?: Array<{ tool_name: string; status: string; message?: string }>) {
  if (!tools) return []
  return tools.filter(t => !HIDDEN_TOOLS.includes(t.tool_name))
}

// 计算工具执行统计
function getToolStats(tools?: Array<{ tool_name: string; status: string; message?: string }>) {
  const visible = getVisibleTools(tools)
  return {
    success: visible.filter(t => t.status === 'applied' || t.status === 'success').length,
    failed: visible.filter(t => t.status === 'failed').length,
  }
}

// 重发用户消息
function resendMessage(msgIndex: number) {
  const msg = messages.value[msgIndex]
  if (!msg || msg.role !== 'user') return
  if (!isConnected.value || isLoading.value) return

  // 删除该消息及之后的所有消息
  messages.value = messages.value.slice(0, msgIndex)

  // 重新发送
  sendUserMessage(msg.content, { enableWebSearch: enableWebSearch.value })
}

// 判断是否是孤单的用户消息（后面没有 AI 回复）
function isOrphanUserMessage(index: number): boolean {
  const msg = messages.value[index]
  if (msg.role !== 'user') return false

  // 如果是最后一条消息且不在加载中，就是孤单的
  if (index === messages.value.length - 1 && !isLoading.value) {
    return true
  }

  return false
}

// ==================== 回溯功能 ====================

/**
 * 判断是否可以回溯到该消息
 * 只有 assistant 消息且不是最后一条才能回溯
 */
function canRevertToMessage(index: number): boolean {
  const msg = messages.value[index]
  if (msg.role !== 'assistant') return false

  // 不能回溯到最后一条消息（没有后续消息可删除）
  if (index >= messages.value.length - 1) return false

  // 不能在加载中或回溯中操作
  if (isLoading.value || isReverting.value) return false

  // 必须有 conversationId 才能持久化
  if (!conversationId.value) return false

  return true
}

/**
 * 回溯到指定消息位置，删除该消息之后的所有对话
 * @param index 消息索引（保留该消息，删除之后的）
 */
async function revertToMessage(index: number) {
  if (!canRevertToMessage(index)) return
  if (!conversationId.value) return

  // 确认操作
  const deletedCount = messages.value.length - index - 1
  if (!confirm(`确定要回溯到此处吗？将删除后续 ${deletedCount} 条消息。`)) {
    return
  }

  isReverting.value = true
  try {
    // 保留的消息数量 = index + 1（包含当前消息）
    const keepCount = index + 1

    // 调用后端 API 持久化截断
    await truncateConversation(props.projectId, conversationId.value, keepCount)

    // 更新前端状态
    messages.value = messages.value.slice(0, keepCount)

    // 清理展开状态
    expandedTools.value.clear()
    expandedActions.value.clear()

    console.log(`[GM] 回溯成功，保留 ${keepCount} 条消息`)
  } catch (error) {
    console.error('回溯失败:', error)
    alert('回溯失败，请重试')
  } finally {
    isReverting.value = false
  }
}

function scrollToBottom() {
  if (messageContainer.value) {
    messageContainer.value.scrollTop = messageContainer.value.scrollHeight
  }
}

function renderMarkdown(content: string): string {
  if (!content) return ''
  // 预处理：直接将 **"..."** 模式转换为 HTML，绕过 marked 解析
  // CommonMark 规范中，** 紧邻中文引号时不满足左侧翼定界符条件
  // 因为 ** 前面是中文字符（非空白非标点），后面是标点，导致解析失败
  let processed = content
    // **"内容"** 或 **"内容"** 模式
    .replace(/\*\*[""]([^""*]+)[""]\*\*/g, `<strong>"$1"</strong>`)
    // **'内容'** 或 **'内容'** 模式
    .replace(/\*\*['']([^''*]+)['']\*\*/g, `<strong>'$1'</strong>`)
    // **「内容」** 模式
    .replace(/\*\*「([^「」*]+)」\*\*/g, `<strong>「$1」</strong>`)
    // **『内容』** 模式
    .replace(/\*\*『([^『』*]+)』\*\*/g, `<strong>『$1』</strong>`)
    // **【内容】** 模式
    .replace(/\*\*【([^【】*]+)】\*\*/g, `<strong>【$1】</strong>`)
    // **（内容）** 模式
    .replace(/\*\*（([^（）*]+)）\*\*/g, `<strong>（$1）</strong>`)
    // **《内容》** 模式
    .replace(/\*\*《([^《》*]+)》\*\*/g, `<strong>《$1》</strong>`)
    // **〈内容〉** 模式
    .replace(/\*\*〈([^〈〉*]+)〉\*\*/g, `<strong>〈$1〉</strong>`)
  return marked.parse(processed, { async: false }) as string
}

// 长内容相关函数
function isLongContent(content: string): boolean {
  return !!content && content.length > LONG_CONTENT_THRESHOLD
}

function truncateContent(content: string): string {
  if (!content || content.length <= LONG_CONTENT_THRESHOLD) return content
  // 找到截断点附近的合适位置（避免截断单词）
  const truncated = content.slice(0, LONG_CONTENT_THRESHOLD)
  const lastSpace = truncated.lastIndexOf(' ')
  const lastNewline = truncated.lastIndexOf('\n')
  const cutPoint = Math.max(lastSpace, lastNewline, LONG_CONTENT_THRESHOLD - 50)
  return truncated.slice(0, cutPoint > 0 ? cutPoint : LONG_CONTENT_THRESHOLD) + '...'
}

function shouldTruncate(content: string, index: number): boolean {
  return isLongContent(content) && !isLastMessage(index)
}

function isLastMessage(index: number): boolean {
  // 找到最后一条 assistant 消息的索引
  for (let i = messages.value.length - 1; i >= 0; i--) {
    if (messages.value[i].role === 'assistant') {
      return index === i
    }
  }
  return false
}

function showFullContent(content: string) {
  fullContentModal.value = { show: true, content }
}

function closeFullContent() {
  fullContentModal.value = { show: false, content: '' }
}

// ==================== Watch ====================

// 持久化输入内容到 localStorage
watch(inputMessage, (value) => {
  if (value) {
    localStorage.setItem(INPUT_STORAGE_KEY, value)
  } else {
    localStorage.removeItem(INPUT_STORAGE_KEY)
  }
})

// 消息变化时滚动到底部
watch([messages, streamingContent], () => {
  nextTick(scrollToBottom)
})

// 当有工具执行成功时，通知父组件刷新数据
watch(executionStats, (stats, oldStats) => {
  // 只在 stats 变化且有成功执行时刷新
  if (stats && stats.success > 0) {
    console.log('[GM] 工具执行完成，刷新数据', stats)
    emit('refresh')
  }
}, { deep: true })

// ==================== 生命周期 ====================

onMounted(async () => {
  connect()

  // 自动加载最新对话
  await loadLatestConversation()
})

// 自动加载最新对话
async function loadLatestConversation() {
  try {
    const conversations = await getConversations(props.projectId)
    if (conversations.length > 0) {
      // 取第一条（最新的）对话
      const latest = conversations[0]
      await selectConversation(latest)
    }
  } catch (error) {
    console.error('自动加载最新对话失败:', error)
  }
}
</script>

<style scoped>
.gm-agent-panel {
  min-height: 400px;
}

.prose :deep(p) {
  margin: 0.5em 0;
}

.prose :deep(ul),
.prose :deep(ol) {
  margin: 0.5em 0;
  padding-left: 1.5em;
}

.prose :deep(code) {
  background-color: #f3f4f6;
  padding: 0.125rem 0.25rem;
  border-radius: 0.25rem;
  font-size: 0.875em;
}

.prose :deep(pre) {
  background-color: #1f2937;
  color: #e5e7eb;
  padding: 1rem;
  border-radius: 0.5rem;
  overflow-x: auto;
}

.prose :deep(pre code) {
  background-color: transparent;
  padding: 0;
}

.prose :deep(hr) {
  margin: 0.75em 0;
}
</style>
