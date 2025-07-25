// pages/ask/[documentId].tsx
import { GetServerSideProps, InferGetServerSidePropsType } from "next";
import Head from "next/head";
import { MdMessage } from "react-icons/md";
import { Button, Div, H1, P, Span } from "style-props-html";
import { css } from "@emotion/react";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import theme from "@/themes/light";
import LiveProgressViewer from "@/components/live-progress-viewer/LiveProgressViewer";
import { useLiveProgressViewer } from "@/components/live-progress-viewer/useLiveProgressViewer";
import LoadingSpinnerOverlay from "@/components/LoadingSpinnerOverlay";

import getEndpoint from "@/utils/getEndpoint";
import { callLiveRoute, callRoute } from "@/utils/rpc";

type DocumentMetadata = {
  title: string;
  author: string;
  description: string | null;
};

type Props = {
  documentId: string;
  documentMetadata: DocumentMetadata;
};

export const getServerSideProps: GetServerSideProps<Props> = async (ctx) => {
  const endpoint = getEndpoint(); // must work server-side (no window)
  const idParam = ctx.params?.documentId;
  const documentId = Array.isArray(idParam)
    ? idParam[0]
    : typeof idParam === "string"
    ? idParam
    : null;

  if (!documentId) {
    return { notFound: true };
  }

  // Let any network / server errors crash → Next.js 500 page
  const documentMetadata = await callRoute<
    { document_id: string },
    DocumentMetadata
  >(endpoint, "/documents/get-metadata", { document_id: documentId });

  // If your backend signals "not found", you can choose 404:
  // if (!documentMetadata) return { notFound: true };

  return { props: { documentId, documentMetadata } };
};

// ------------ Client component ---------------

const askFormSchema = z.object({
  question: z.string().nonempty("Please enter a question."),
});
type AskFormSchema = z.infer<typeof askFormSchema>;

const buttonInteractionCss = css`
  transformorigin: center;
  transition: transform 0.1s ease-in-out;
  cursor: pointer;
  transform: scale(1);

  &:not(:disabled):hover {
    transform: scale(1.05);
  }
  &:not(:disabled):active {
    transform: scale(0.95);
  }
  &:disabled {
    cursor: not-allowed;
    opacity: 0.4;
  }
`;

export default function AskPage({
  documentId,
  documentMetadata,
}: InferGetServerSidePropsType<typeof getServerSideProps>) {
  const endpoint = getEndpoint();

  // const [answer, setAnswer] = useState<string | null>(null);

  const {
    progressMessages,
    containerRef: progressContainerRef,
    addProgressMessage,
    clearProgressMessages,
    upsertProgressBarByTitle,
  } = useLiveProgressViewer();

  const {
    register,
    handleSubmit,
    reset,
    formState: {
      errors,
      isValid,
      isSubmitting,
      isSubmitSuccessful,
      isSubmitted,
    },
  } = useForm<AskFormSchema>({
    resolver: zodResolver(askFormSchema),
    defaultValues: { question: "" },
    mode: "onChange",
  });

  async function onSubmit(data: AskFormSchema) {
    const question = data.question;
    addProgressMessage({ kind: "string", text: "Asking AI..." });
    try {
      await callLiveRoute<
        { document_id: string; question: string },
        { answer: string }
      >(
        endpoint,
        "/documents/ask",
        { document_id: documentId, question },
        {
          onUpdate: ({ message }) => {
            addProgressMessage({ kind: "string", text: message });
          },
          onProgress: ({ current, total, name }) => {
            if (name) {
              upsertProgressBarByTitle(name, current, total, {
                showAsPercent: true,
                titleStyle: { color: "blue" }
              });
            }
          },
        }
      );

      addProgressMessage({
        kind: "string",
        text: "Done thinking.",
        color: "green",
      });
    } catch (err) {
      console.error(err);
      addProgressMessage({
        kind: "string",
        text: "Failed to answer your question.",
        color: "red",
      });
      throw err;
    }
  }

  return (
    <>
      <Head>
        <title>Ask a Question</title>
        <meta
          name="description"
          content="Ask a question about a previously uploaded document."
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.png" />
      </Head>

      <Div
        width="100dvw"
        height="100dvh"
        display="flex"
        flexDirection="column"
        alignItems="center"
        justifyContent="center"
      >
        <Div
          width="75vw"
          height="75vh"
          display="grid"
          background={theme.colors.card.body.bg}
          borderRadius="1rem"
          gridTemplateRows="auto 1fr"
          boxShadow={`4px 4px 4px 0px ${theme.colors.card.body.shadow}`}
        >
          <H1
            width="100%"
            fontSize="3rem"
            height="5rem"
            lineHeight="5rem"
            textAlign="center"
            background={theme.colors.card.header.bg}
            color={theme.colors.card.header.text}
            borderRadius="1rem 1rem 0 0"
            boxShadow={`4px 4px 4px 0px ${theme.colors.card.body.shadow}`}
          >
            Ask a Question
          </H1>

          <Div
            borderRadius="0 0 1rem 1rem"
            color={theme.colors.card.body.text}
            width="75vw"
            display="grid"
            gridTemplateColumns="auto auto"
          >
            <Div
              display="flex"
              flexDirection="column"
              alignItems="center"
              gap="0.5rem"
              padding="1rem"
              width={isSubmitted || isSubmitting ? "30vw" : "75vw"}
            >
              <Div
                display="flex"
                flexDirection="column"
                gap="0.5rem"
                width="100%"
              >
                {/* Metadata is guaranteed here */}
                <Div
                  fontSize="2rem"
                  fontWeight="bold"
                  width="100%"
                  textAlign="center"
                >
                  {documentMetadata.title}
                </Div>
                <Div
                  fontSize="1.5rem"
                  fontStyle="italic"
                  width="100%"
                  textAlign="center"
                >
                  {documentMetadata.author}
                </Div>
                {documentMetadata.description && (
                  <P
                    whiteSpace="pre-wrap"
                    width="100%"
                    maxWidth="80rem"
                    fontSize="1rem"
                  >
                    {documentMetadata.description}
                  </P>
                )}

                <input
                  {...register("question")}
                  disabled={isSubmitting || isSubmitted}
                  placeholder="Ask a question..."
                  style={{
                    padding: "0.5rem",
                    border: "1px solid #ccc",
                    borderRadius: "0.25rem",
                  }}
                />
                {errors.question && (
                  <P color="red">{errors.question.message}</P>
                )}
              </Div>

              <Button
                onClick={() => handleSubmit(onSubmit)()}
                disabled={!isValid || isSubmitting || isSubmitted}
                display="flex"
                alignItems="center"
                gap="0.5rem"
                padding="0.5rem 1rem"
                borderRadius="0.5rem"
                border="2px solid blue"
                color="blue"
                background="white"
                boxShadow={`4px 4px 4px 0px ${theme.colors.card.body.shadow}`}
                position="relative"
                css={buttonInteractionCss}
              >
                <MdMessage />
                <Span>
                  {isSubmitting
                    ? "Answering…"
                    : isSubmitSuccessful
                    ? "Done answering."
                    : isSubmitted && !isSubmitSuccessful
                    ? "Failed to answer."
                    : "Ask"}
                </Span>
                {isSubmitting && <LoadingSpinnerOverlay size="1rem" />}
              </Button>

              {isSubmitted && !isSubmitSuccessful && (
                <Button
                  fontSize="1rem"
                  onClick={() => {
                    // reset submission state, keep current field values
                    reset(undefined, { keepValues: true });
                    handleSubmit(onSubmit)();
                  }}
                  border="none"
                  color="red"
                  background="transparent"
                  css={buttonInteractionCss}
                  textDecoration="underline"
                >
                  Try Again
                </Button>
              )}

              {(isSubmitSuccessful || (isSubmitted && !isSubmitSuccessful)) && (
                <Button
                  fontSize="1rem"
                  onClick={() => {
                    reset(); // wipe back to defaultValues
                    clearProgressMessages();
                  }}
                  border="none"
                  color="blue"
                  background="transparent"
                  css={buttonInteractionCss}
                  textDecoration="underline"
                >
                  Ask Another Question
                </Button>
              )}
            </Div>

            <Div
              width={isSubmitted || isSubmitting ? "45vw" : "0"}
              transition="width 0.3s ease-in-out"
              display="grid"
              gridTemplateRows="auto 1fr"
              height="calc(75vh - 5rem)"
            >
              <Div></Div>
              <LiveProgressViewer
                width="100%"
                ref={progressContainerRef}
                progressMessages={progressMessages}
              />
            </Div>
          </Div>
        </Div>
      </Div>
    </>
  );
}
