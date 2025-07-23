import Head from "next/head";
import { useCallback, useEffect, useRef, useState } from "react";
import { MdMessage } from "react-icons/md";
import { Button, Div, H1, H2, P, Span } from "style-props-html";
import { useRouter } from "next/router";

import LiveProgressViewer from "@/components/live-progress-viewer/LiveProgressViewer";
import { useLiveProgressViewer } from "@/components/live-progress-viewer/useLiveProgressViewer";
import LoadingSpinnerOverlay from "@/components/LoadingSpinnerOverlay";
import theme from "@/themes/light";

import getEndpoint from "@/utils/getEndpoint";
import { css } from "@emotion/react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { callRoute } from "@/utils/rpc";

const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20MB

const ALLOWED_TYPES = {
  "text/plain": {
    description: "Plain Text",
    extensions: ["txt"],
  },
};

const MAX_UPLOAD_CHUNK_SIZE = 16 * 1024; // 16 kB

const buttonInteractionCss = css`
  transformorigin: center;
  transition: transform 0.1s ease-in-out;
  cursor: pointer;
  transform: scale(1);

  /* only apply scale effects when not disabled */
  &:not(:disabled):hover {
    transform: scale(1.05);
  }
  &:not(:disabled):active {
    transform: scale(0.95);
  }

  /* disabled styling */
  &:disabled {
    cursor: not-allowed;
    opacity: 0.4; /* optional visual cue */
  }
`;

// Zod schema for metadata
const askFormSchema = z.object({
  question: z.string().nonempty("Please enter a question."),
});
type AskFormSchema = z.infer<typeof askFormSchema>;

type DocumentMetadata = {
  title: string;
  author: string;
  description: string | null;
};

export default function Ask() {
  const endpoint = getEndpoint();

  const inputRef = useRef<HTMLInputElement>(null);

  const router = useRouter();

  const { documentId } = router.query as { documentId?: string };

  const [documentMetadata, setDocumentMetadata] =
    useState<DocumentMetadata | null>(null);

  const [documentMetadataError, setDocumentMetadataError] = useState<
    string | null
  >(null);


   const fetchDocumentMetadata = useCallback(async function() {
    if(!documentId) return;
    try {
      setDocumentMetadata(
        await callRoute<
          {
            document_id: string;
          },
          DocumentMetadata
        >(endpoint, "/documents/get-metadata", { document_id: documentId })
      );
    } catch (err) {
      console.error(err);
      if (err instanceof Error) {
        setDocumentMetadataError(
          `Failed to fetch document metadata: ${err.message}`
        );
      } else {
        setDocumentMetadataError("Failed to fetch document metadata.");
      }
    }
  },[documentId])

  useEffect(() => {
    fetchDocumentMetadata();
  }, [documentId]);

  const {
    progressMessages,
    containerRef: progressContainerRef,
    addProgressMessage,
    updateMessageById,
    clearProgressMessages,
  } = useLiveProgressViewer();

  // react-hook-form setup
  const {
    register,
    handleSubmit,
    setValue,
    watch,
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
    mode: "onChange", // get live `isValid`
  });

  // Combined upload procedure including metadata
  async function onSubmit(data: AskFormSchema) {
    const question = data.question;

    try {
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
          {documentMetadataError ? (
            <Div
              fontSize="1.5rem"
              fontWeight="bold"
              color="red"
              background="white"
              borderRadius="0.5rem"
              padding="0.5rem"
            >
              {documentMetadataError}
            </Div>
          ) : (
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
                  {documentMetadata && (
                    <>
                      <Div fontSize="2rem" fontWeight="bold">
                        {documentMetadata.title}
                      </Div>
                      <Div
                        fontSize="1.5rem"
                        fontWeight="normal"
                        fontStyle="italic"
                      >
                        {documentMetadata.author}
                      </Div>
                      {documentMetadata.description && (
                        <P whiteSpace="pre-wrap">
                          {documentMetadata.description}
                        </P>
                      )}
                    </>
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
                  onClick={() => {
                    handleSubmit(onSubmit)();
                  }}
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
                      // 1) reset submission state, keep the current field values:
                      reset(undefined, {
                        keepValues: true,
                        keepErrors: true,
                        keepDirty: true,
                        keepTouched: true,
                        keepIsValid: true,
                        // submitCount will reset to 0 so isSubmitted → false
                        keepSubmitCount: false,
                      });

                      // 2) immediately re‑invoke your submit handler
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
                {(isSubmitSuccessful ||
                  (isSubmitted && !isSubmitSuccessful)) && (
                  <Button
                    fontSize="1rem"
                    onClick={() => {
                      reset(); // ← wipe back to defaultValues
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
              >
                <LiveProgressViewer
                  width="100%"
                  height="calc(75vh - 5rem)"
                  ref={progressContainerRef}
                  progressMessages={progressMessages}
                />
              </Div>
            </Div>
          )}
        </Div>
      </Div>
    </>
  );
}
