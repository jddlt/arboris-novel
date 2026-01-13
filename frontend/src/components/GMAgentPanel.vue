<template>
  <!-- 主面板容器 - 不再使用 Teleport，直接作为 flex 子元素 -->
  <div class="flex flex-col h-full bg-white border-l border-gray-200 overflow-hidden">
    <!-- 头部 -->
    <div class="flex items-center justify-between px-4 h-16 bg-gradient-to-r from-indigo-500 to-purple-600 text-white flex-shrink-0">
      <div class="flex items-center gap-2">
        <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
          <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zm0 16a3 3 0 01-3-3h6a3 3 0 01-3 3z"/>
        </svg>
        <span class="font-semibold">剧本大师GM</span>
      </div>
      <div class="flex items-center gap-2">
        <!-- 清除当前对话按钮 -->
        <button
          @click="clearCurrentConversation"
          class="p-1.5 hover:bg-white/20 rounded-lg transition-colors"
          title="清除对话"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
          </svg>
        </button>
        <!-- 历史对话按钮 -->
        <button
          @click="toggleHistoryPanel"
          class="p-1.5 hover:bg-white/20 rounded-lg transition-colors"
          :class="showHistoryPanel ? 'bg-white/20' : ''"
          title="历史对话"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
        </button>
        <!-- 新建对话按钮 -->
        <button
          @click="startNewConversation"
          class="p-1.5 hover:bg-white/20 rounded-lg transition-colors"
          title="新建对话"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
          </svg>
        </button>
        <!-- 关闭按钮 -->
        <button
          @click="$emit('close')"
          class="p-1.5 hover:bg-white/20 rounded-lg transition-colors"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- 历史对话下拉面板 -->
    <Transition
      enter-active-class="transition-all duration-200 ease-out"
      leave-active-class="transition-all duration-150 ease-in"
      enter-from-class="opacity-0 -translate-y-2"
      leave-to-class="opacity-0 -translate-y-2"
    >
      <div v-if="showHistoryPanel" class="border-b border-gray-200 bg-gray-50 max-h-64 overflow-y-auto flex-shrink-0">
        <!-- 加载中 -->
        <div v-if="isLoadingHistory" class="flex items-center justify-center py-6">
          <div class="w-5 h-5 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
          <span class="ml-2 text-sm text-gray-500">加载中...</span>
        </div>

        <!-- 无历史记录 -->
        <div v-else-if="historyList.length === 0" class="py-6 text-center text-gray-500 text-sm">
          暂无历史对话
        </div>

        <!-- 历史列表 -->
        <div v-else class="divide-y divide-gray-200">
          <button
            v-for="conv in historyList"
            :key="conv.id"
            @click="selectConversation(conv)"
            class="w-full px-4 py-3 text-left hover:bg-indigo-50 transition-colors flex items-center justify-between group"
            :class="conversationId === conv.id ? 'bg-indigo-50' : ''"
          >
            <div class="flex-1 min-w-0">
              <div class="text-sm font-medium text-gray-900 truncate">{{ conv.title }}</div>
              <div class="text-xs text-gray-500 mt-0.5">{{ conv.message_count }} 条消息</div>
            </div>
            <div class="flex-shrink-0 ml-3">
              <span class="text-xs text-gray-400">{{ formatTime(conv.updated_at) }}</span>
              <div v-if="conversationId === conv.id" class="mt-1">
                <span class="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-indigo-100 text-indigo-700">当前</span>
              </div>
            </div>
          </button>
        </div>
      </div>
    </Transition>

    <!-- 消息列表 -->
    <div ref="messageContainer" class="flex-1 overflow-y-auto p-4 space-y-4">
      <!-- 欢迎消息 -->
      <div v-if="messages.length === 0" class="text-center text-gray-500 py-8">
        <svg class="w-16 h-16 mx-auto mb-4 text-indigo-300" fill="currentColor" viewBox="0 0 20 20">
          <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zm0 16a3 3 0 01-3-3h6a3 3 0 01-3 3z"/>
        </svg>
        <p class="text-lg font-medium text-gray-700 mb-2">你好！我是剧本大师GM</p>
        <p class="text-sm text-gray-500 mb-4">你的全能小说创作助手</p>
        <div class="inline-flex flex-col items-start space-y-2 text-xs text-gray-400">
          <div class="flex items-center gap-2">
            <span class="w-1.5 h-1.5 bg-indigo-400 rounded-full flex-shrink-0"></span>
            <span>角色、关系、世界观管理</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="w-1.5 h-1.5 bg-purple-400 rounded-full flex-shrink-0"></span>
            <span>章节大纲规划与卷分配</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="w-1.5 h-1.5 bg-pink-400 rounded-full flex-shrink-0"></span>
            <span>直接撰写或修改章节内容</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="w-1.5 h-1.5 bg-amber-400 rounded-full flex-shrink-0"></span>
            <span>创意灵感与剧情建议</span>
          </div>
        </div>
      </div>

      <!-- 消息气泡 -->
      <div
        v-for="(msg, index) in messages"
        :key="index"
        :class="['flex', msg.role === 'user' ? 'justify-end' : 'justify-start']"
      >
        <div
          :class="[
            'max-w-[85%] rounded-2xl px-4 py-2.5 text-sm',
            msg.role === 'user'
              ? 'bg-indigo-500 text-white rounded-br-md'
              : 'bg-gray-100 text-gray-800 rounded-bl-md'
          ]"
        >
          <!-- 只读工具调用记录（折叠显示，在消息内容上方） -->
          <div v-if="msg.role !== 'user' && msg.readOnlyTools && msg.readOnlyTools.length > 0" class="mb-2">
            <div
              v-for="(tool, toolIdx) in msg.readOnlyTools"
              :key="`${index}-${toolIdx}`"
              class="mb-1.5 last:mb-0"
            >
              <!-- 折叠状态：只显示工具名和查询标签 -->
              <button
                @click="toggleReadOnlyTool(`${index}-${toolIdx}`)"
                class="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 transition-colors"
              >
                <svg
                  class="w-3 h-3 transition-transform flex-shrink-0"
                  :class="expandedReadOnlyTools.has(`${index}-${toolIdx}`) ? 'rotate-90' : ''"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                </svg>
                <span class="font-medium">{{ getToolLabel(tool.name) }}</span>
                <span class="px-1 py-0.5 bg-blue-100 text-blue-600 rounded text-[10px]">查询</span>
              </button>
              <!-- 展开状态：显示参数和结果 -->
              <Transition
                enter-active-class="transition-all duration-200 ease-out"
                leave-active-class="transition-all duration-150 ease-in"
                enter-from-class="opacity-0 max-h-0"
                leave-to-class="opacity-0 max-h-0"
                enter-to-class="opacity-100 max-h-96"
                leave-from-class="opacity-100 max-h-96"
              >
                <div
                  v-if="expandedReadOnlyTools.has(`${index}-${toolIdx}`)"
                  class="mt-1.5 ml-4 text-xs bg-blue-50/70 rounded px-2 py-1.5 overflow-hidden"
                >
                  <!-- 参数 -->
                  <div v-if="tool.params && Object.keys(tool.params).length > 0" class="space-y-0.5 mb-1.5">
                    <div v-for="(value, key) in tool.params" :key="key" class="text-blue-700">
                      <span class="text-blue-500">{{ formatParamKey(String(key)) }}:</span>
                      <span class="ml-1">{{ formatParamValue(value) }}</span>
                    </div>
                  </div>
                  <!-- 结果（可能很长，截断显示） -->
                  <div class="text-gray-600 border-t border-blue-100 pt-1">
                    <span class="text-blue-500">结果:</span>
                    <span class="ml-1 whitespace-pre-wrap break-words">{{ tool.result.length > 200 ? tool.result.slice(0, 200) + '...' : tool.result }}</span>
                  </div>
                </div>
              </Transition>
            </div>
          </div>
          <!-- 消息内容（支持 Markdown，长文本截断） -->
          <div
            v-if="msg.role === 'user'"
            class="whitespace-pre-wrap break-words"
          >{{ isLongContent(msg.content) ? truncateContent(msg.content) : msg.content }}</div>
          <!-- 用户消息中的图片（显示在文字下方） -->
          <div v-if="msg.role === 'user' && msg.images && msg.images.length > 0" class="flex gap-2 mt-2 flex-wrap">
            <img
              v-for="(img, imgIdx) in msg.images"
              :key="imgIdx"
              :src="img.preview"
              @click="showImagePreview(img.preview)"
              class="w-20 h-20 object-cover rounded-lg border border-indigo-300 cursor-pointer hover:opacity-80 transition-opacity"
              alt="发送的图片"
            />
          </div>
          <div
            v-if="msg.role !== 'user'"
            class="prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-pre:my-2 prose-code:px-1 prose-code:py-0.5 prose-code:bg-gray-200 prose-code:rounded prose-code:text-xs"
            v-html="renderMarkdown(isLongContent(msg.content) ? truncateContent(msg.content) : msg.content)"
          ></div>
          <button
            v-if="isLongContent(msg.content)"
            @click="showFullContent(msg.content)"
            :class="[
              'mt-2 text-xs font-medium underline',
              msg.role === 'user' ? 'text-indigo-200 hover:text-white' : 'text-indigo-600 hover:text-indigo-800'
            ]"
          >
            查看全文（{{ msg.content.length }} 字）
          </button>

          <!-- 重发按钮（仅 assistant 消息显示） -->
          <div
            v-if="msg.role === 'assistant' && !isLoading && !isStreaming"
            class="flex items-center gap-2 mt-2 pt-1"
          >
            <button
              @click="regenerateMessage(index)"
              class="flex items-center gap-1 text-xs text-gray-400 hover:text-indigo-600 transition-colors"
              title="重新生成回复"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
              </svg>
              <span>重发</span>
            </button>
          </div>

          <!-- 待执行操作 -->
          <div v-if="msg.actions && msg.actions.length > 0" class="mt-3 space-y-2">
            <div
              v-for="action in msg.actions"
              :key="action.action_id"
              class="bg-white/90 rounded-lg p-2.5 border border-gray-200"
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
                        :class="expandedActions.has(action.action_id) ? 'rotate-180' : ''"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                      </svg>
                    </button>
                  </div>
                  <p class="text-xs text-gray-600 mt-0.5">{{ action.preview }}</p>
                </div>
                <div v-if="action.status === 'pending'" class="flex gap-1 flex-shrink-0">
                  <button
                    @click="applyAction(action.action_id)"
                    :disabled="isApplying"
                    class="p-1 text-green-600 hover:bg-green-50 rounded transition-colors disabled:opacity-50"
                    title="应用"
                  >
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
                    </svg>
                  </button>
                  <button
                    @click="discardAction(action.action_id)"
                    :disabled="isApplying"
                    class="p-1 text-red-600 hover:bg-red-50 rounded transition-colors disabled:opacity-50"
                    title="放弃"
                  >
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
                    </svg>
                  </button>
                </div>
                <span v-else :class="getStatusClass(action.status)" class="text-xs px-1.5 py-0.5 rounded flex-shrink-0">
                  {{ getStatusLabel(action.status) }}
                </span>
              </div>
              <!-- 展开的详情内容 -->
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
                    <span class="text-gray-500">{{ formatParamKey(String(key)) }}:</span>
                    <span class="text-gray-700 ml-1 whitespace-pre-wrap break-words">{{ formatParamValue(value) }}</span>
                  </div>
                </div>
              </Transition>
            </div>
            <!-- 单条消息批量操作按钮 -->
            <div
              v-if="msg.actions && msg.actions.filter(a => a.status === 'pending').length > 1"
              class="flex justify-end gap-2 mt-2 pt-2 border-t border-gray-100"
            >
              <button
                @click="applyMessageActions(index)"
                :disabled="isApplying"
                class="px-2 py-1 text-xs bg-green-500 text-white rounded hover:bg-green-600 disabled:opacity-50 transition-colors"
              >
                全部应用 ({{ msg.actions.filter(a => a.status === 'pending').length }})
              </button>
              <button
                @click="discardMessageActions(index)"
                :disabled="isApplying"
                class="px-2 py-1 text-xs bg-gray-400 text-white rounded hover:bg-gray-500 disabled:opacity-50 transition-colors"
              >
                全部放弃
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 流式输出中 -->
      <div v-if="isStreaming && streamingContent" class="flex justify-start">
        <div class="max-w-[85%] rounded-2xl rounded-bl-md px-4 py-2.5 bg-gray-100 text-gray-800 text-sm">
          <div
            class="prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-pre:my-2 prose-code:px-1 prose-code:py-0.5 prose-code:bg-gray-200 prose-code:rounded prose-code:text-xs"
            v-html="renderMarkdown(streamingContent)"
          ></div>
          <span class="animate-pulse text-gray-400">|</span>
        </div>
      </div>

      <!-- 正在执行只读工具 -->
      <div v-if="executingTool" class="flex justify-start">
        <div class="max-w-[85%] rounded-2xl rounded-bl-md px-4 py-3 bg-blue-50 border border-blue-200 text-sm">
          <div class="flex items-center gap-2 text-blue-700 mb-2">
            <div class="w-4 h-4 border-2 border-blue-300 border-t-blue-600 rounded-full animate-spin"></div>
            <span class="font-medium">{{ getToolLabel(executingTool.name) }}</span>
            <span class="text-blue-500 text-xs">查询中...</span>
          </div>
          <!-- 展示工具参数 -->
          <div v-if="executingTool.params && Object.keys(executingTool.params).length > 0" class="text-xs text-blue-600 bg-blue-100/50 rounded px-2 py-1.5 space-y-0.5">
            <div v-for="(value, key) in executingTool.params" :key="key">
              <span class="text-blue-500">{{ formatParamKey(String(key)) }}:</span>
              <span class="ml-1">{{ formatParamValue(value) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 等待确认提示 -->
      <div v-if="awaitingContinue && !isLoading && !isStreaming" class="flex justify-center">
        <div class="bg-amber-50 border border-amber-200 rounded-lg px-4 py-2 text-sm text-amber-700 flex items-center gap-2">
          <svg class="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
          </svg>
          <span>请确认上方操作后，助手将根据执行结果继续</span>
        </div>
      </div>

      <!-- 加载中（等待回复或流式输出还没内容时） -->
      <div v-if="isLoading && !streamingContent" class="flex justify-start">
        <div class="bg-gray-100 rounded-2xl rounded-bl-md px-4 py-3">
          <div class="flex gap-1">
            <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
            <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
            <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入框 -->
    <div class="p-3 border-t border-gray-200 flex-shrink-0">
      <!-- 图片预览区 -->
      <div v-if="pastedImages.length > 0" class="flex gap-2 mb-2 flex-wrap">
        <div
          v-for="(img, index) in pastedImages"
          :key="index"
          class="relative group"
        >
          <img
            :src="img.preview"
            class="w-16 h-16 object-cover rounded-lg border border-gray-200"
            alt="待发送图片"
          />
          <button
            @click="removeImage(index)"
            class="absolute -top-1.5 -right-1.5 w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity text-xs"
          >
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
        <div class="text-xs text-gray-400 self-end">Ctrl+V 粘贴图片（最多4张）</div>
      </div>
      <div class="flex gap-2 items-start">
        <textarea
          v-model="inputMessage"
          @keydown.enter.exact.prevent="sendMessage"
          @paste="handlePaste"
          :disabled="isLoading"
          placeholder="输入消息，可粘贴图片..."
          rows="3"
          class="flex-1 px-3 py-2 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent disabled:bg-gray-100 text-sm"
        ></textarea>
        <div class="flex flex-col items-center gap-2">
          <button
            @click="sendMessage"
            :disabled="(!inputMessage.trim() && pastedImages.length === 0) || isLoading"
            class="px-4 py-3 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
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
  </div>

  <!-- 全文查看 Modal - 仍然使用 Teleport -->
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-200"
      leave-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div v-if="fullContentModal.show" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60] flex items-center justify-center p-4" @click.self="closeFullContent">
        <div class="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[80vh] flex flex-col">
          <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200">
            <h3 class="text-lg font-semibold text-gray-900">完整内容</h3>
            <button
              @click="closeFullContent"
              class="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>
          <div class="flex-1 overflow-y-auto px-6 py-4">
            <div
              class="prose prose-sm max-w-none text-gray-700 leading-relaxed"
              v-html="renderMarkdown(fullContentModal.content)"
            ></div>
          </div>
          <div class="px-6 py-3 border-t border-gray-200 bg-gray-50 rounded-b-2xl">
            <p class="text-xs text-gray-500 text-center">共 {{ fullContentModal.content.length }} 字</p>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>

  <!-- 图片预览 Modal -->
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-200"
      leave-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div v-if="imagePreviewModal.show" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-[70] flex items-center justify-center p-4" @click.self="closeImagePreview">
        <div class="relative max-w-[90vw] max-h-[90vh]">
          <img
            :src="imagePreviewModal.src"
            class="max-w-full max-h-[85vh] object-contain rounded-lg shadow-2xl"
            alt="图片预览"
          />
          <button
            @click="closeImagePreview"
            class="absolute -top-3 -right-3 w-8 h-8 bg-white text-gray-600 rounded-full flex items-center justify-center shadow-lg hover:bg-gray-100 transition-colors"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted } from 'vue'
import { marked } from 'marked'
import {
  streamChatWithGM,
  continueChatWithGM,
  applyActions,
  discardActions,
  getConversations,
  getConversationDetail,
  archiveConversation,
  type GMPendingAction,
  type ConversationMessage,
  type ConversationSummary,
  type ActionResult,
} from '@/api/gm'

// 配置 marked
marked.setOptions({
  breaks: true,
  gfm: true,
})

// 渲染 Markdown
function renderMarkdown(content: string): string {
  try {
    return marked.parse(content) as string
  } catch {
    return content
  }
}

const props = defineProps<{
  projectId: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'refresh'): void
}>()

// localStorage 键名
const STORAGE_KEY_PREFIX = 'gm_agent_chat_'
const getStorageKey = () => `${STORAGE_KEY_PREFIX}${props.projectId}`

// 图片数据接口
interface ImageData {
  base64: string
  mimeType: string
  preview: string // 用于预览的 data URL
}

// 状态
const messages = ref<(ConversationMessage & {
  actions?: GMPendingAction[];
  images?: ImageData[];
  readOnlyTools?: { name: string; params: Record<string, unknown>; result: string }[];
})[]>([])
const inputMessage = ref('')
const isLoading = ref(false)
const isStreaming = ref(false)
const streamingContent = ref('')
const isApplying = ref(false)
const expandedActions = ref<Set<string>>(new Set())
const conversationId = ref<string | null>(null)
const enableWebSearch = ref(false)
const messageContainer = ref<HTMLElement | null>(null)
const pastedImages = ref<ImageData[]>([]) // 待发送的粘贴图片

// 历史对话列表状态
const showHistoryPanel = ref(false)
const historyList = ref<ConversationSummary[]>([])
const isLoadingHistory = ref(false)

// 全文查看 Modal 状态
const fullContentModal = ref<{ show: boolean; content: string }>({
  show: false,
  content: '',
})

// 图片预览 Modal 状态
const imagePreviewModal = ref<{ show: boolean; src: string }>({
  show: false,
  src: '',
})

// Agent 是否在等待确认后继续
const awaitingContinue = ref(false)

// 当前正在执行的只读工具信息
const executingTool = ref<{ name: string; params: Record<string, unknown> } | null>(null)

// 已执行的只读工具调用列表（当前轮对话中）
const executedReadOnlyTools = ref<{ name: string; params: Record<string, unknown>; result: string }[]>([])

// 展开的只读工具ID集合（按消息索引+工具索引组合）
const expandedReadOnlyTools = ref<Set<string>>(new Set())

// 长文本阈值（字符数）
const LONG_CONTENT_THRESHOLD = 500

// 保存对话到 localStorage
function saveToLocalStorage() {
  try {
    const data = {
      messages: messages.value,
      conversationId: conversationId.value,
      enableWebSearch: enableWebSearch.value,
      timestamp: Date.now(),
    }
    localStorage.setItem(getStorageKey(), JSON.stringify(data))
  } catch (error) {
    console.error('保存对话失败:', error)
  }
}

// 从 localStorage 恢复对话
function loadFromLocalStorage() {
  try {
    const stored = localStorage.getItem(getStorageKey())
    if (stored) {
      const data = JSON.parse(stored)
      // 检查数据是否过期（7天）
      const maxAge = 7 * 24 * 60 * 60 * 1000
      if (Date.now() - data.timestamp < maxAge) {
        messages.value = data.messages || []
        conversationId.value = data.conversationId || null
        enableWebSearch.value = data.enableWebSearch || false
        scrollToBottom()
      } else {
        // 数据过期，清除
        localStorage.removeItem(getStorageKey())
      }
    }
  } catch (error) {
    console.error('恢复对话失败:', error)
  }
}

// 判断是否为长文本
function isLongContent(content: string): boolean {
  return content.length > LONG_CONTENT_THRESHOLD
}

// 截断内容
function truncateContent(content: string): string {
  if (content.length <= LONG_CONTENT_THRESHOLD) return content
  return content.slice(0, LONG_CONTENT_THRESHOLD) + '...'
}

// 显示完整内容
function showFullContent(content: string) {
  fullContentModal.value = { show: true, content }
}

// 关闭全文查看
function closeFullContent() {
  fullContentModal.value = { show: false, content: '' }
}

// 显示图片预览
function showImagePreview(src: string) {
  imagePreviewModal.value = { show: true, src }
}

// 关闭图片预览
function closeImagePreview() {
  imagePreviewModal.value = { show: false, src: '' }
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
}

// 计算待执行操作数量
const pendingActionsCount = computed(() => {
  let count = 0
  for (const msg of messages.value) {
    if (msg.actions) {
      count += msg.actions.filter(a => a.status === 'pending').length
    }
  }
  return count
})

// 获取工具标签
function getToolLabel(toolName: string): string {
  return toolLabels[toolName] || toolName
}

// 获取状态标签
function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    applied: '已应用',
    discarded: '已放弃',
    failed: '失败',
    pending: '待执行',
  }
  return labels[status] || status
}

// 获取状态样式
function getStatusClass(status: string): string {
  const classes: Record<string, string> = {
    applied: 'bg-green-100 text-green-700',
    discarded: 'bg-gray-100 text-gray-500',
    failed: 'bg-red-100 text-red-700',
  }
  return classes[status] || 'bg-gray-100 text-gray-600'
}

// 参数名映射
const paramKeyLabels: Record<string, string> = {
  name: '名称',
  identity: '身份',
  personality: '性格',
  goals: '目标',
  abilities: '能力',
  relationship_to_protagonist: '与主角关系',
  extra: '额外信息',
  title: '标题',
  genre: '题材',
  style: '风格',
  tone: '基调',
  target_audience: '目标读者',
  one_sentence_summary: '一句话简介',
  full_synopsis: '故事概要',
  world_setting: '世界观设定',
  world_setting_patch: '世界观更新',
  content: '内容',
  summary: '摘要',
  chapter_number: '章节号',
  chapter_numbers: '章节号列表',
  from_character: '角色A',
  to_character: '角色B',
  description: '描述',
  relation_type: '关系类型',
  include_full_content: '包含完整内容',
  new_content: '新内容',
  modification_reason: '修改原因',
}

// 格式化参数键名
function formatParamKey(key: string): string {
  return paramKeyLabels[key] || key
}

// 格式化参数值
function formatParamValue(value: unknown): string {
  if (value === null || value === undefined) return '(空)'
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value, null, 2)
    } catch {
      return String(value)
    }
  }
  return String(value)
}

// 切换操作详情展开状态
function toggleActionDetails(actionId: string) {
  if (expandedActions.value.has(actionId)) {
    expandedActions.value.delete(actionId)
  } else {
    expandedActions.value.add(actionId)
  }
}

// 切换只读工具展开状态
function toggleReadOnlyTool(toolKey: string) {
  if (expandedReadOnlyTools.value.has(toolKey)) {
    expandedReadOnlyTools.value.delete(toolKey)
  } else {
    expandedReadOnlyTools.value.add(toolKey)
  }
}

// 滚动到底部
function scrollToBottom() {
  nextTick(() => {
    if (messageContainer.value) {
      messageContainer.value.scrollTop = messageContainer.value.scrollHeight
    }
  })
}

// 处理粘贴事件（支持图片粘贴）
function handlePaste(event: ClipboardEvent) {
  const items = event.clipboardData?.items
  if (!items) return

  for (const item of items) {
    if (item.type.startsWith('image/')) {
      event.preventDefault() // 阻止默认粘贴行为
      const file = item.getAsFile()
      if (!file) continue

      // 限制图片数量
      if (pastedImages.value.length >= 4) {
        console.warn('最多只能添加4张图片')
        return
      }

      // 读取图片并转换为 base64
      const reader = new FileReader()
      reader.onload = (e) => {
        const dataUrl = e.target?.result as string
        if (!dataUrl) return

        // 解析 data URL：data:image/png;base64,xxxxx
        const matches = dataUrl.match(/^data:(image\/[^;]+);base64,(.+)$/)
        if (matches) {
          pastedImages.value.push({
            mimeType: matches[1],
            base64: matches[2],
            preview: dataUrl,
          })
        }
      }
      reader.readAsDataURL(file)
    }
  }
}

// 移除待发送的图片
function removeImage(index: number) {
  pastedImages.value.splice(index, 1)
}

// 发送消息
async function sendMessage() {
  const content = inputMessage.value.trim()
  const imagesToSend = [...pastedImages.value] // 复制当前图片列表
  if ((!content && imagesToSend.length === 0) || isLoading.value) return

  inputMessage.value = ''
  pastedImages.value = [] // 清空待发送图片
  isLoading.value = true
  isStreaming.value = true
  streamingContent.value = ''
  awaitingContinue.value = false

  // 添加用户消息（包含图片）
  messages.value.push({
    role: 'user',
    content,
    images: imagesToSend.length > 0 ? imagesToSend : undefined,
  })
  scrollToBottom()

  try {
    let pendingActions: GMPendingAction[] = []
    let finalContent = ''
    // 清空上一轮的只读工具记录
    executedReadOnlyTools.value = []

    // 构造发送给 API 的图片数据（只需要 base64 和 mimeType）
    const apiImages = imagesToSend.map(img => ({
      base64: img.base64,
      mime_type: img.mimeType,
    }))

    // 临时保存当前执行中的工具信息
    let currentExecutingTool: { name: string; params: Record<string, unknown> } | null = null

    for await (const event of streamChatWithGM(props.projectId, content, {
      conversationId: conversationId.value || undefined,
      enableWebSearch: enableWebSearch.value,
      images: apiImages.length > 0 ? apiImages : undefined,
    })) {
      if (event.type === 'start') {
        conversationId.value = event.conversation_id
      } else if (event.type === 'content') {
        streamingContent.value += event.content
        scrollToBottom()
      } else if (event.type === 'tool_executing') {
        // 正在执行只读工具
        currentExecutingTool = { name: event.tool_name, params: event.params }
        executingTool.value = currentExecutingTool
        scrollToBottom()
      } else if (event.type === 'tool_result') {
        // 只读工具执行完成，保存到已执行列表
        if (currentExecutingTool) {
          executedReadOnlyTools.value.push({
            name: currentExecutingTool.name,
            params: currentExecutingTool.params,
            result: event.result,
          })
        }
        executingTool.value = null
        currentExecutingTool = null
        scrollToBottom()
      } else if (event.type === 'pending_actions') {
        pendingActions = event.actions
      } else if (event.type === 'done') {
        finalContent = event.message
        // 检查是否需要在应用后继续
        if (event.awaiting_confirmation) {
          awaitingContinue.value = true
        }
      } else if (event.type === 'error') {
        throw new Error(event.error)
      }
    }

    isStreaming.value = false
    executingTool.value = null

    // 添加助手消息（包含只读工具调用记录）
    messages.value.push({
      role: 'assistant',
      content: finalContent || streamingContent.value,
      actions: pendingActions,
      readOnlyTools: executedReadOnlyTools.value.length > 0 ? [...executedReadOnlyTools.value] : undefined,
    })
    // 清空临时记录
    executedReadOnlyTools.value = []
    scrollToBottom()
  } catch (error) {
    isStreaming.value = false
    const errorMessage = error instanceof Error ? error.message : '发送失败'
    messages.value.push({
      role: 'assistant',
      content: `抱歉，发生了错误：${errorMessage}`,
    })
    scrollToBottom()
  } finally {
    isLoading.value = false
    streamingContent.value = ''
  }
}

// 应用单个操作
async function applyAction(actionId: string) {
  // 防止重复提交和与 continue 操作冲突
  if (isApplying.value || isLoading.value) return
  isApplying.value = true

  try {
    const result = await applyActions(props.projectId, [actionId])

    // 更新操作状态
    for (const msg of messages.value) {
      if (msg.actions) {
        for (const action of msg.actions) {
          if (action.action_id === actionId) {
            const res = result.results.find(r => r.action_id === actionId)
            action.status = res?.success ? 'applied' : 'failed'
          }
        }
      }
    }

    // 通知刷新数据
    emit('refresh')

    // 如果 Agent 还在等待继续，自动继续对话并传递执行结果
    if (awaitingContinue.value && conversationId.value) {
      await continueAfterApply(result.results)
    }
  } catch (error) {
    console.error('应用操作失败:', error)
  } finally {
    isApplying.value = false
  }
}

// 在应用操作后继续对话
async function continueAfterApply(actionResults: ActionResult[]) {
  if (!conversationId.value || isLoading.value) return

  isLoading.value = true
  isStreaming.value = true
  streamingContent.value = ''
  // 清空上一轮的只读工具记录
  executedReadOnlyTools.value = []

  try {
    let pendingActions: GMPendingAction[] = []
    let finalContent = ''
    // 临时保存当前执行中的工具信息
    let currentExecutingTool: { name: string; params: Record<string, unknown> } | null = null

    for await (const event of continueChatWithGM(
      props.projectId,
      conversationId.value,
      actionResults,
      { enableWebSearch: enableWebSearch.value }
    )) {
      if (event.type === 'content') {
        streamingContent.value += event.content
        scrollToBottom()
      } else if (event.type === 'tool_executing') {
        currentExecutingTool = { name: event.tool_name, params: event.params }
        executingTool.value = currentExecutingTool
        scrollToBottom()
      } else if (event.type === 'tool_result') {
        // 只读工具执行完成，保存到已执行列表
        if (currentExecutingTool) {
          executedReadOnlyTools.value.push({
            name: currentExecutingTool.name,
            params: currentExecutingTool.params,
            result: event.result,
          })
        }
        executingTool.value = null
        currentExecutingTool = null
        scrollToBottom()
      } else if (event.type === 'pending_actions') {
        pendingActions = event.actions
      } else if (event.type === 'done') {
        finalContent = event.message
        awaitingContinue.value = !!event.awaiting_confirmation
      } else if (event.type === 'error') {
        throw new Error(event.error)
      }
    }

    isStreaming.value = false
    executingTool.value = null

    // 添加助手消息（包含只读工具调用记录）
    if (finalContent || streamingContent.value) {
      messages.value.push({
        role: 'assistant',
        content: finalContent || streamingContent.value,
        actions: pendingActions,
        readOnlyTools: executedReadOnlyTools.value.length > 0 ? [...executedReadOnlyTools.value] : undefined,
      })
      // 清空临时记录
      executedReadOnlyTools.value = []
      scrollToBottom()
    }
  } catch (error) {
    isStreaming.value = false
    executingTool.value = null
    const errorMessage = error instanceof Error ? error.message : '继续对话失败'
    messages.value.push({
      role: 'assistant',
      content: `抱歉，发生了错误：${errorMessage}`,
    })
    scrollToBottom()
  } finally {
    isLoading.value = false
    streamingContent.value = ''
  }
}

// 放弃单个操作
async function discardAction(actionId: string) {
  if (isApplying.value || isLoading.value) return
  isApplying.value = true

  try {
    await discardActions(props.projectId, [actionId])

    // 更新操作状态
    for (const msg of messages.value) {
      if (msg.actions) {
        for (const action of msg.actions) {
          if (action.action_id === actionId) {
            action.status = 'discarded'
          }
        }
      }
    }
  } catch (error) {
    console.error('放弃操作失败:', error)
  } finally {
    isApplying.value = false
  }
}

// 应用指定消息的所有待执行操作
async function applyMessageActions(msgIndex: number) {
  const msg = messages.value[msgIndex]
  if (!msg?.actions || isApplying.value || isLoading.value) return

  const pendingIds = msg.actions
    .filter(a => a.status === 'pending')
    .map(a => a.action_id)

  if (pendingIds.length === 0) return

  isApplying.value = true
  try {
    const result = await applyActions(props.projectId, pendingIds)

    for (const action of msg.actions) {
      const res = result.results.find(r => r.action_id === action.action_id)
      if (res) {
        action.status = res.success ? 'applied' : 'failed'
      }
    }

    emit('refresh')

    // 如果 Agent 还在等待继续，自动继续对话并传递执行结果
    if (awaitingContinue.value && conversationId.value) {
      await continueAfterApply(result.results)
    }
  } catch (error) {
    console.error('批量应用失败:', error)
  } finally {
    isApplying.value = false
  }
}

// 放弃指定消息的所有待执行操作
async function discardMessageActions(msgIndex: number) {
  const msg = messages.value[msgIndex]
  if (!msg?.actions || isApplying.value || isLoading.value) return

  const pendingIds = msg.actions
    .filter(a => a.status === 'pending')
    .map(a => a.action_id)

  if (pendingIds.length === 0) return

  isApplying.value = true
  try {
    await discardActions(props.projectId, pendingIds)

    for (const action of msg.actions) {
      if (action.status === 'pending') {
        action.status = 'discarded'
      }
    }
  } catch (error) {
    console.error('批量放弃失败:', error)
  } finally {
    isApplying.value = false
  }
}

// 应用所有待执行操作
async function applyAllPending() {
  // 防止与 continue 操作冲突
  if (isApplying.value || isLoading.value) return

  const pendingIds: string[] = []
  for (const msg of messages.value) {
    if (msg.actions) {
      for (const action of msg.actions) {
        if (action.status === 'pending') {
          pendingIds.push(action.action_id)
        }
      }
    }
  }

  if (pendingIds.length === 0) return

  isApplying.value = true
  try {
    const result = await applyActions(props.projectId, pendingIds)

    // 更新所有操作状态
    for (const msg of messages.value) {
      if (msg.actions) {
        for (const action of msg.actions) {
          const res = result.results.find(r => r.action_id === action.action_id)
          if (res) {
            action.status = res.success ? 'applied' : 'failed'
          }
        }
      }
    }

    emit('refresh')

    // 如果 Agent 还在等待继续，自动继续对话并传递执行结果
    if (awaitingContinue.value && conversationId.value) {
      await continueAfterApply(result.results)
    }
  } catch (error) {
    console.error('批量应用失败:', error)
  } finally {
    isApplying.value = false
  }
}

// 放弃所有待执行操作
async function discardAllPending() {
  if (isApplying.value || isLoading.value) return

  const pendingIds: string[] = []
  for (const msg of messages.value) {
    if (msg.actions) {
      for (const action of msg.actions) {
        if (action.status === 'pending') {
          pendingIds.push(action.action_id)
        }
      }
    }
  }

  if (pendingIds.length === 0) return

  isApplying.value = true
  try {
    await discardActions(props.projectId, pendingIds)

    for (const msg of messages.value) {
      if (msg.actions) {
        for (const action of msg.actions) {
          if (action.status === 'pending') {
            action.status = 'discarded'
          }
        }
      }
    }
  } catch (error) {
    console.error('批量放弃失败:', error)
  } finally {
    isApplying.value = false
  }
}

// 重发消息（重新生成 assistant 回复）
async function regenerateMessage(assistantMsgIndex: number) {
  if (isLoading.value || isStreaming.value) return

  // 找到该 assistant 消息前面的 user 消息
  let userMsgIndex = -1
  for (let i = assistantMsgIndex - 1; i >= 0; i--) {
    if (messages.value[i].role === 'user') {
      userMsgIndex = i
      break
    }
  }

  if (userMsgIndex === -1) {
    console.error('未找到对应的用户消息')
    return
  }

  const userMsg = messages.value[userMsgIndex]
  const userContent = userMsg.content
  const userImages = userMsg.images ? [...userMsg.images] : []

  // 删除从 assistant 消息开始的所有后续消息（保留用户消息）
  messages.value = messages.value.slice(0, assistantMsgIndex)

  // 重新发送请求
  isLoading.value = true
  isStreaming.value = true
  streamingContent.value = ''
  awaitingContinue.value = false
  executedReadOnlyTools.value = []

  try {
    let pendingActions: GMPendingAction[] = []
    let finalContent = ''

    const apiImages = userImages.map(img => ({
      base64: img.base64,
      mime_type: img.mimeType,
    }))

    let currentExecutingTool: { name: string; params: Record<string, unknown> } | null = null

    for await (const event of streamChatWithGM(props.projectId, userContent, {
      conversationId: conversationId.value || undefined,
      enableWebSearch: enableWebSearch.value,
      images: apiImages.length > 0 ? apiImages : undefined,
    })) {
      if (event.type === 'start') {
        conversationId.value = event.conversation_id
      } else if (event.type === 'content') {
        streamingContent.value += event.content
        scrollToBottom()
      } else if (event.type === 'tool_executing') {
        currentExecutingTool = { name: event.tool_name, params: event.params }
        executingTool.value = currentExecutingTool
        scrollToBottom()
      } else if (event.type === 'tool_result') {
        if (currentExecutingTool) {
          executedReadOnlyTools.value.push({
            name: currentExecutingTool.name,
            params: currentExecutingTool.params,
            result: event.result,
          })
        }
        executingTool.value = null
        currentExecutingTool = null
        scrollToBottom()
      } else if (event.type === 'pending_actions') {
        pendingActions = event.actions
      } else if (event.type === 'done') {
        finalContent = event.message
        if (event.awaiting_confirmation) {
          awaitingContinue.value = true
        }
      } else if (event.type === 'error') {
        throw new Error(event.error)
      }
    }

    isStreaming.value = false
    executingTool.value = null

    messages.value.push({
      role: 'assistant',
      content: finalContent || streamingContent.value,
      actions: pendingActions,
      readOnlyTools: executedReadOnlyTools.value.length > 0 ? [...executedReadOnlyTools.value] : undefined,
    })
    executedReadOnlyTools.value = []
    scrollToBottom()
  } catch (error) {
    isStreaming.value = false
    const errorMessage = error instanceof Error ? error.message : '重新生成失败'
    messages.value.push({
      role: 'assistant',
      content: `抱歉，发生了错误：${errorMessage}`,
    })
    scrollToBottom()
  } finally {
    isLoading.value = false
    streamingContent.value = ''
  }
}

// 新建对话
function startNewConversation() {
  messages.value = []
  conversationId.value = null
  streamingContent.value = ''
  showHistoryPanel.value = false
  // 清除 localStorage 中的对话
  localStorage.removeItem(getStorageKey())
}

// 清除当前对话（归档后清空，不保留到历史列表）
async function clearCurrentConversation() {
  // 如果有对话 ID，先归档（这样不会出现在默认历史列表中）
  if (conversationId.value) {
    try {
      await archiveConversation(props.projectId, conversationId.value)
    } catch (error) {
      console.error('归档对话失败:', error)
      // 即使归档失败，也继续清除本地状态
    }
  }

  // 清除本地状态
  messages.value = []
  conversationId.value = null
  streamingContent.value = ''
  showHistoryPanel.value = false
  localStorage.removeItem(getStorageKey())
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
    isLoading.value = true
    const detail = await getConversationDetail(props.projectId, conv.id)
    messages.value = detail.messages.map(msg => ({
      ...msg,
      actions: msg.actions?.map(a => ({
        action_id: a.action_id,
        tool_name: a.tool_name || '',
        params: a.params || {},
        preview: a.preview || '',
        status: a.status as GMPendingAction['status'],
      })),
    }))
    conversationId.value = conv.id
    showHistoryPanel.value = false
    saveToLocalStorage()
    scrollToBottom()
  } catch (error) {
    console.error('加载对话详情失败:', error)
  } finally {
    isLoading.value = false
  }
}

// 格式化时间
function formatTime(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))

  if (days === 0) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } else if (days === 1) {
    return '昨天'
  } else if (days < 7) {
    return `${days}天前`
  } else {
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
  }
}

// 组件挂载时恢复对话
onMounted(() => {
  loadFromLocalStorage()
})

// 监听消息变化，自动滚动并保存
watch(messages, () => {
  scrollToBottom()
  saveToLocalStorage()
}, { deep: true })

// 监听 conversationId 变化，保存
watch(conversationId, saveToLocalStorage)
</script>
