"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.useModels = useModels;
const react_1 = require("react");
const buildModelProfiles_1 = require("../application/llm/buildModelProfiles");
const groupModelsByCapability_1 = require("../application/llm/groupModelsByCapability");
function useModels(rpc, connected) {
    const [catalog, setCatalog] = (0, react_1.useState)([]);
    const [loading, setLoading] = (0, react_1.useState)(true);
    const [showLegacy, setShowLegacy] = (0, react_1.useState)(false);
    const fetchModels = (0, react_1.useCallback)(async () => {
        setLoading(true);
        try {
            const data = await rpc('provider.models');
            setCatalog(data.models ?? []);
        }
        catch {
            setCatalog([]);
        }
        finally {
            setLoading(false);
        }
    }, [rpc]);
    (0, react_1.useEffect)(() => {
        if (connected) {
            void fetchModels();
        }
    }, [connected, fetchModels]);
    const models = (0, react_1.useMemo)(() => (0, buildModelProfiles_1.buildModelProfiles)(catalog), [catalog]);
    const grouped = (0, react_1.useMemo)(() => (0, groupModelsByCapability_1.groupModelsByCapability)(models, showLegacy), [models, showLegacy]);
    return { models, grouped, loading, showLegacy, setShowLegacy, refetch: fetchModels };
}
