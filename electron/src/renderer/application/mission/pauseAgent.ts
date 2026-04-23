import type {
  PauseAgentInput,
  PauseAgentPort,
  PauseAgentResult,
} from './pauseAgentPort';

export async function pauseAgent(
  port: PauseAgentPort,
  input: PauseAgentInput,
): Promise<PauseAgentResult> {
  return port(input);
}
