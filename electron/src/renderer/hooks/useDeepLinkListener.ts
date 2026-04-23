import { useEffect, useRef } from 'react';
import { handleDeepLink } from '../application/deepLink/handleDeepLink';
import { parseDeepLink } from '../domain/deepLink/deepLink';
import { useConfigStore } from '../stores/configStore';
import { useHashNavigation } from './useHashNavigation';

export function useDeepLinkListener(): void {
  const { navigate } = useHashNavigation();
  const reauthPolicyRef = useRef(useConfigStore.getState().deepLinkReauth);
  const sessionReauthedRef = useRef(false);

  useEffect(() => {
    const unsubscribePolicy = useConfigStore.subscribe((state) => {
      reauthPolicyRef.current = state.deepLinkReauth;
    });
    return () => {
      unsubscribePolicy();
    };
  }, []);

  useEffect(() => {
    const bridge = window.electronAPI?.deepLink;
    if (!bridge?.onDeepLink) {
      return undefined;
    }

    const unsubscribe = bridge.onDeepLink((uri: string) => {
      void handleDeepLink(uri, {
        parseUri: parseDeepLink,
        navigate,
        warnInvalid: (error, rawUri) => {
          // eslint-disable-next-line no-console
          console.warn(`[deep-link] reject ${error}: ${rawUri}`);
        },
        getReauthPolicy: () => reauthPolicyRef.current,
        requestReauth: async () => {
          // Sole-user environment: no real re-auth surface yet; treat as approved.
          // Future multi-user: open a modal and await user confirmation.
          return true;
        },
        hasReauthedThisSession: () => sessionReauthedRef.current,
        markSessionReauthed: () => {
          sessionReauthedRef.current = true;
        },
      });
    });

    return () => {
      unsubscribe();
    };
  }, [navigate]);
}
