import { useEffect, useState } from 'react';
import { useWs } from './WsProvider';

export interface SemanticMetricView {
  metricId: string;
  displayName: string;
  owner: string;
  ownerContact: string | null;
  definition: string;
  synonyms: string[];
  grain: string | null;
  unit: string | null;
  direction: string | null;
  caveats: string[];
  verifiedQueryIds: string[];
  typicalRange: [number, number] | null;
  calculationSources: string[];
}

export interface SemanticGlossaryView {
  termId: string;
  canonicalForm: string;
  definition: string;
  synonyms: string[];
  abbreviations: string[];
  linkedMetricIds: string[];
}

export interface SemanticVerifiedQueryView {
  vqId: string;
  dialect: string;
  description: string;
  verifiedBy: string;
  lastVerified: string | null;
  referencedTables: string[];
  verificationEvidence: string | null;
}

export interface SemanticTrustTableView {
  fqtn: string;
  grade: string;
  owner: string;
  description: string;
  gradeRationale: string;
  lastAudited: string | null;
}

export interface SemanticSourceView {
  query: string;
  loading: boolean;
  error: string | null;
  notFound: boolean;
  metric: SemanticMetricView | null;
  glossaryMatches: SemanticGlossaryView[];
  verifiedQuery: SemanticVerifiedQueryView | null;
  trustAction: string | null;
  trustTables: SemanticTrustTableView[];
  trustWarnings: string[];
}

const EMPTY_SOURCE: SemanticSourceView = {
  query: '',
  loading: false,
  error: null,
  notFound: false,
  metric: null,
  glossaryMatches: [],
  verifiedQuery: null,
  trustAction: null,
  trustTables: [],
  trustWarnings: [],
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null ? value as Record<string, unknown> : null;
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim().length > 0 ? value : null;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0);
}

function asTupleRange(value: unknown): [number, number] | null {
  if (!Array.isArray(value) || value.length !== 2) {
    return null;
  }
  const [start, end] = value;
  return typeof start === 'number' && typeof end === 'number' ? [start, end] : null;
}

function uniqueStrings(values: readonly string[]): string[] {
  return Array.from(new Set(values.filter((item) => item.trim().length > 0)));
}

function extractMetric(value: unknown): SemanticMetricView | null {
  const record = asRecord(value);
  if (!record) {
    return null;
  }

  const calculation = asRecord(record.calculation);
  const numerator = asRecord(calculation?.numerator);
  const denominator = asRecord(calculation?.denominator);
  const calculationSources = uniqueStrings(
    [asString(numerator?.source), asString(denominator?.source)].filter(
      (item): item is string => item !== null
    )
  );

  const metricId = asString(record.metric_id);
  const displayName = asString(record.display_name);
  const owner = asString(record.owner);
  const definition = asString(record.definition);

  if (!metricId || !displayName || !owner || !definition) {
    return null;
  }

  return {
    metricId,
    displayName,
    owner,
    ownerContact: asString(record.owner_contact),
    definition,
    synonyms: asStringArray(record.synonyms),
    grain: asString(record.grain),
    unit: asString(record.unit),
    direction: asString(record.direction),
    caveats: asStringArray(record.caveats),
    verifiedQueryIds: asStringArray(record.verified_query_ids),
    typicalRange: asTupleRange(record.typical_range),
    calculationSources,
  };
}

function extractGlossaryTerm(value: unknown): SemanticGlossaryView | null {
  const record = asRecord(value);
  if (!record) {
    return null;
  }

  const termId = asString(record.term_id);
  const canonicalForm = asString(record.canonical_form);
  const definition = asString(record.definition);

  if (!termId || !canonicalForm || !definition) {
    return null;
  }

  return {
    termId,
    canonicalForm,
    definition,
    synonyms: asStringArray(record.synonyms),
    abbreviations: asStringArray(record.abbreviations),
    linkedMetricIds: asStringArray(record.linked_metric_ids),
  };
}

function extractVerifiedQuery(value: unknown): SemanticVerifiedQueryView | null {
  const record = asRecord(value);
  if (!record) {
    return null;
  }

  const query = asRecord(record.query);
  if (!query) {
    return null;
  }

  const vqId = asString(query.vq_id);
  const dialect = asString(query.dialect);
  const description = asString(query.description);
  const verifiedBy = asString(query.verified_by);

  if (!vqId || !dialect || !description || !verifiedBy) {
    return null;
  }

  return {
    vqId,
    dialect,
    description,
    verifiedBy,
    lastVerified: asString(query.last_verified),
    referencedTables: asStringArray(query.referenced_tables),
    verificationEvidence: asString(query.verification_evidence),
  };
}

function extractTrustTable(value: unknown): SemanticTrustTableView | null {
  const record = asRecord(value);
  if (!record) {
    return null;
  }

  const fqtn = asString(record.fqtn);
  const grade = asString(record.grade);
  const owner = asString(record.owner);
  const description = asString(record.description);
  const gradeRationale = asString(record.grade_rationale);

  if (!fqtn || !grade || !owner || !description || !gradeRationale) {
    return null;
  }

  return {
    fqtn,
    grade,
    owner,
    description,
    gradeRationale,
    lastAudited: asString(record.last_audited),
  };
}

export function useSemanticSource(metricQuery: string | null): SemanticSourceView {
  const { rpc, status } = useWs();
  const [source, setSource] = useState<SemanticSourceView>(EMPTY_SOURCE);

  useEffect(() => {
    const query = metricQuery?.trim() ?? '';
    if (!query) {
      setSource(EMPTY_SOURCE);
      return;
    }

    if (status !== 'connected') {
      setSource({
        ...EMPTY_SOURCE,
        query,
        error: 'Semantic source unavailable while the backend is disconnected.',
      });
      return;
    }

    let cancelled = false;
    setSource({
      ...EMPTY_SOURCE,
      query,
      loading: true,
    });

    const load = async () => {
      try {
        const lookupPayload = await rpc('semantic.lookupMetric', { query });
        if (cancelled) {
          return;
        }

        const lookup = asRecord(lookupPayload.lookup);
        const matches = Array.isArray(lookup?.matches) ? lookup.matches : [];
        const bestMatch = matches
          .map((item) => extractMetric(asRecord(item)?.metric))
          .find((item): item is SemanticMetricView => item !== null);
        const glossaryMatches = Array.isArray(lookup?.glossaryMatches)
          ? lookup.glossaryMatches
              .map((item) => extractGlossaryTerm(item))
              .filter((item): item is SemanticGlossaryView => item !== null)
          : [];

        if (!bestMatch) {
          setSource({
            ...EMPTY_SOURCE,
            query,
            notFound: true,
            glossaryMatches,
          });
          return;
        }

        let verifiedQuery: SemanticVerifiedQueryView | null = null;
        const verifiedQueryPayload = await rpc('semantic.getVerifiedQuery', {
          metricId: bestMatch.metricId,
          dialect: 'postgres',
        });
        if (!cancelled) {
          verifiedQuery = extractVerifiedQuery(verifiedQueryPayload.verifiedQuery);
        }

        const trustTargets = uniqueStrings([
          ...bestMatch.calculationSources,
          ...(verifiedQuery?.referencedTables ?? []),
        ]);

        let trustAction: string | null = null;
        let trustTables: SemanticTrustTableView[] = [];
        let trustWarnings: string[] = [];
        if (trustTargets.length > 0) {
          const trustPayload = await rpc('semantic.getTrust', { fqtns: trustTargets });
          if (!cancelled) {
            const trust = asRecord(trustPayload.trust);
            trustAction = asString(trust?.action);
            trustTables = Array.isArray(trust?.tables)
              ? trust.tables
                  .map((item) => extractTrustTable(item))
                  .filter((item): item is SemanticTrustTableView => item !== null)
              : [];
            trustWarnings = asStringArray(trust?.warnings);
          }
        }

        if (cancelled) {
          return;
        }

        setSource({
          query,
          loading: false,
          error: null,
          notFound: false,
          metric: bestMatch,
          glossaryMatches,
          verifiedQuery,
          trustAction,
          trustTables,
          trustWarnings,
        });
      } catch (error) {
        if (cancelled) {
          return;
        }
        setSource({
          ...EMPTY_SOURCE,
          query,
          error: error instanceof Error ? error.message : 'Semantic source lookup failed.',
        });
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, [metricQuery, rpc, status]);

  return source;
}
