import {
  CAPABILITY_GROUP_DEFINITIONS,
  type CapabilityGroup,
  type ModelCapabilityGroup,
  type ModelProfile,
} from '../../domain/llm/modelCapability';

function compareModels(left: ModelProfile, right: ModelProfile): number {
  if (left.legacy !== right.legacy) {
    return left.legacy ? 1 : -1;
  }
  if (left.maxContext !== right.maxContext) {
    return right.maxContext - left.maxContext;
  }
  return left.displayName.localeCompare(right.displayName);
}

export function groupModelsByCapability(
  models: readonly ModelProfile[],
  showLegacy: boolean,
): ModelCapabilityGroup[] {
  const grouped = new Map<CapabilityGroup, ModelProfile[]>(
    CAPABILITY_GROUP_DEFINITIONS.map((definition) => [definition.id, []]),
  );

  for (const model of models) {
    if (!showLegacy && model.legacy) {
      continue;
    }
    grouped.get(model.capabilityGroup)?.push(model);
  }

  return CAPABILITY_GROUP_DEFINITIONS.map((definition) => ({
    ...definition,
    models: [...(grouped.get(definition.id) ?? [])].sort(compareModels),
  }));
}
