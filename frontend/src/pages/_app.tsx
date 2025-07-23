import "@/styles/globals.css";
import { CacheProvider, EmotionCache } from '@emotion/react';
import createEmotionCache from '@/createEmotionCache';

const clientCache = createEmotionCache();

export default function MyApp({
  Component,
  pageProps,
  emotionCache = clientCache,
}: {
  Component: any;
  pageProps: any;
  emotionCache?: EmotionCache;
}) {
  return (
    <CacheProvider value={emotionCache}>
      <Component {...pageProps} />
    </CacheProvider>
  );
}
