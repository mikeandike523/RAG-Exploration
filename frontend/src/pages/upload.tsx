import Head from "next/head";

import {Div} from 'style-props-html'


export default function Home() {
  return (
    <>
      <Head>
        <title>Upload a Document</title>
        <meta name="description" content="Upload a document to be processed by the AI." />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.png" />
      </Head>
      <Div width="100dvw" height="100dvh" display="grid">

      </Div>
    </>
  );
}
