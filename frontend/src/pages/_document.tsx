import Document, {
  Html,
  Head,
  Main,
  NextScript,
  DocumentContext,
  DocumentInitialProps,
} from 'next/document';
import createEmotionServer from '@emotion/server/create-instance';
import createEmotionCache from '@/createEmotionCache';
import React from 'react';

export default class MyDocument extends Document {
  static async getInitialProps(ctx: DocumentContext): Promise<DocumentInitialProps> {
    const originalRenderPage = ctx.renderPage;

    const cache = createEmotionCache();
    const { extractCriticalToChunks } = createEmotionServer(cache);

    ctx.renderPage = () =>
      originalRenderPage({
        enhanceApp: (App: any) =>
          function EnhanceApp(props) {
            return <App emotionCache={cache} {...props} />;
          },
      });

    const initialProps = await Document.getInitialProps(ctx);

    // Grab the critical CSS
    const chunks = extractCriticalToChunks(initialProps.html);

    // (React 18 safety) clear what we've already inserted so subsequent renders don’t duplicate
    cache.inserted = {};

    const emotionStyleTags = chunks.styles.map((style) => (
      <style
        key={style.key}
        data-emotion={`${style.key} ${style.ids.join(' ')}`}
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML={{ __html: style.css }}
      />
    ));

    return {
      ...initialProps,
      styles: (
        <>
          {initialProps.styles}
          {emotionStyleTags}
        </>
      ),
    };
  }

  render() {
    return (
      <Html>
        <Head>
          {/* Optional, but guarantees correct order when mixing with Tailwind/global.css */}
          <meta name="emotion-insertion-point" content="" />
        </Head>
        <body>
          <Main />
          <NextScript />
        </body>
      </Html>
    );
  }
}
