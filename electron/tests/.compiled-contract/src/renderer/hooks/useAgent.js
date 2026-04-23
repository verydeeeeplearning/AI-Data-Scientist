"use strict";
/**
 * Agent hook — sidebar data fetching and config mutations.
 *
 * Fetches files, status, and handles model/mode changes via WS RPC.
 * Subscribes to file.created events to keep sidebar up to date.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.useAgent = useAgent;
const react_1 = require("react");
const WsProvider_1 = require("./WsProvider");
const uploadFile_1 = require("../application/workspace/uploadFile");
const uploadApi_1 = require("../infrastructure/workspace/uploadApi");
const agentStore_1 = require("../stores/agentStore");
const chatStore_1 = require("../stores/chatStore");
const filesStore_1 = require("../stores/filesStore");
function useAgent() {
    const { status, rpc, on } = (0, WsProvider_1.useWs)();
    // Extract only the action functions via selectors (stable references)
    const currentModel = (0, agentStore_1.useAgentStore)((s) => s.model);
    const currentQualityPreset = (0, agentStore_1.useAgentStore)((s) => s.qualityPreset);
    const updateFromStatus = (0, agentStore_1.useAgentStore)((s) => s.updateFromStatus);
    const setMode = (0, agentStore_1.useAgentStore)((s) => s.setMode);
    const resetConversation = (0, chatStore_1.useChatStore)((s) => s.resetConversation);
    const setFiles = (0, filesStore_1.useFilesStore)((s) => s.setFiles);
    const setLoading = (0, filesStore_1.useFilesStore)((s) => s.setLoading);
    const addFileFromEvent = (0, filesStore_1.useFilesStore)((s) => s.addFileFromEvent);
    const removeFileByPath = (0, filesStore_1.useFilesStore)((s) => s.removeFileByPath);
    // Fetch status on connect
    (0, react_1.useEffect)(() => {
        if (status !== 'connected')
            return;
        rpc('status.get')
            .then((data) => updateFromStatus(data))
            .catch((err) => console.warn('[useAgent] status.get failed:', err));
    }, [status, rpc, updateFromStatus]);
    // Fetch files on connect
    (0, react_1.useEffect)(() => {
        if (status !== 'connected')
            return;
        setLoading(true);
        rpc('files.list', {})
            .then((data) => {
            const entries = data.files ?? [];
            setFiles(entries);
        })
            .catch((err) => console.warn('[useAgent] files.list failed:', err))
            .finally(() => setLoading(false));
    }, [status, rpc, setFiles, setLoading]);
    // Subscribe to file.created events
    (0, react_1.useEffect)(() => {
        return on('file.created', (payload) => {
            addFileFromEvent(payload.path ?? '', payload.type ?? '', payload.size ?? 0);
        });
    }, [on, addFileFromEvent]);
    // Remove file from sidebar immediately when backend confirms deletion.
    (0, react_1.useEffect)(() => {
        return on('file.deleted', (payload) => {
            removeFileByPath(payload.path ?? '');
        });
    }, [on, removeFileByPath]);
    // Refresh from the source of truth whenever the backend says the workspace changed.
    (0, react_1.useEffect)(() => {
        return on('workspace.changed', () => {
            void rpc('files.list', {})
                .then((data) => {
                setFiles(data.files ?? []);
            })
                .catch((err) => console.warn('[useAgent] workspace refresh failed:', err));
        });
    }, [on, rpc, setFiles]);
    // Refresh files manually
    const refreshFiles = (0, react_1.useCallback)(async () => {
        setLoading(true);
        try {
            const data = await rpc('files.list', {});
            setFiles(data.files ?? []);
        }
        finally {
            setLoading(false);
        }
    }, [rpc, setFiles, setLoading]);
    // Change model
    const changeModel = (0, react_1.useCallback)(async (model) => {
        if (model === currentModel)
            return;
        try {
            await rpc('chat.abort');
        }
        catch (err) {
            console.warn('[useAgent] abort before model change failed:', err);
        }
        await rpc('config.set', { path: 'provider.default_model', value: model });
        resetConversation(true);
        updateFromStatus(await rpc('status.get'));
    }, [rpc, currentModel, resetConversation, updateFromStatus]);
    const changeQualityPreset = (0, react_1.useCallback)(async (preset) => {
        if (preset === currentQualityPreset) {
            return;
        }
        try {
            await rpc('chat.abort');
        }
        catch (err) {
            console.warn('[useAgent] abort before preset change failed:', err);
        }
        await rpc('config.set', { path: 'provider.quality_preset', value: preset });
        resetConversation(true);
        updateFromStatus(await rpc('status.get'));
    }, [rpc, currentQualityPreset, resetConversation, updateFromStatus]);
    // Change mode
    const changeMode = (0, react_1.useCallback)(async (mode) => {
        await rpc('config.set', { path: 'agent.mode', value: mode });
        setMode(mode);
    }, [rpc, setMode]);
    // Upload file (FE-03: client-side size validation before base64 conversion)
    const MAX_UPLOAD_SIZE = 100 * 1024 * 1024; // 100MB — matches server limit
    const uploadFile = (0, react_1.useCallback)(async (file) => {
        if (file.size > MAX_UPLOAD_SIZE) {
            throw new Error(`File exceeds the 100 MB upload limit (${file.size} bytes).`);
        }
        try {
            const result = await (0, uploadFile_1.uploadFileWithPreview)(file, uploadApi_1.uploadWorkspaceFile);
            await refreshFiles();
            if (!result.workspacePath) {
                throw new Error('Backend did not return an uploaded path.');
            }
            return result;
        }
        catch (err) {
            console.error('[useAgent] upload failed:', err);
            throw err instanceof Error ? err : new Error(String(err));
        }
    }, [refreshFiles]);
    return {
        status: status,
        rpc,
        refreshFiles,
        changeModel,
        changeQualityPreset,
        changeMode,
        uploadFile,
    };
}
