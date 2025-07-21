import { blobToBase64 } from "@maruware/blob-to-base64";
import Head from "next/head";
import { DragEvent, useRef, useState } from "react";
import { MdCloudUpload } from "react-icons/md";
import { Button, Div, H1, P, Span } from "style-props-html";

import { useLiveProgressViewer } from "@/components/live-progress-viewer/useLiveProgressViewer";
import LoadingSpinnerOverlay from "@/components/LoadingSpinnerOverlay";
import theme from "@/themes/light";
import { FileStreamer } from "@/utils/FileStreamer";
import { callRoute } from "@/utils/rpc";
import { SerializableObject } from "@/utils/serialization";
import {
  ProgressBarMessage,
  ProgressMessage,
} from "@/components/live-progress-viewer/types";
import LiveProgressViewer from "@/components/live-progress-viewer/LiveProgressViewer";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { css } from "@emotion/react";

// Just development for now,
// In the future, may need a tunnel
const endpoint = "http://localhost:5000";

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
const uplaodFormSchema = z.object({
  file: z
    .instanceof(File, { message: "A file is required" })
    .refine(
      (f) => f.size <= MAX_FILE_SIZE,
      `File must be ≤ ${MAX_FILE_SIZE / (1024 * 1024)}MB`
    )
    .refine(
      (f) => Object.keys(ALLOWED_TYPES).includes(f.type),
      "Unsupported file type"
    ),
  title: z.string().nonempty("Title is required"),
  author: z.string().nonempty("Author is required"),
  description: z.string().optional(),
});
type UploadFormData = z.infer<typeof uplaodFormSchema>;

export default function Upload() {
  const inputRef = useRef<HTMLInputElement>(null);

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
  } = useForm<UploadFormData>({
    resolver: zodResolver(uplaodFormSchema),
    defaultValues: { title: "", author: "", description: "", file: undefined },
    mode: "onChange", // get live `isValid`
  });

  const currentlySelectedFile = watch("file");

  const handleFilePicker = (files: FileList): void => {
    const selected = files[0];
    if (!selected) return;
    // let Zod catch invalid name/size/type
    setValue("file", selected, { shouldValidate: true, shouldDirty: true });
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    handleFilePicker(e.dataTransfer.files);
  };

  const onDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  const onClickZone = () => {
    inputRef.current?.click();
  };

  // Combined upload procedure including metadata
  async function onSubmit(data: UploadFormData) {
    const file = data.file;
    const title = data.title;
    const author = data.author;
    const description = data.description;

    try {

      addProgressMessage({ kind: "string", text: "Uploading..." });
      addProgressMessage({ kind: "string", text: "Creating object..." });

      const objectId = await callRoute<SerializableObject, string>(
        endpoint,
        "/files/upload/new-object",
        {
          name: file.name,
          mime_type: file.type,
          size: file.size,
        }
      );

      addProgressMessage({
        kind: "string",
        text: `Created object with id ${objectId}`,
      });

      const progressBarId = addProgressMessage({
        kind: "progressBar",
        title: "Uploading",
        showAsPercent: true,
        max: file.size,
        current: 0,
        precision: 0,
        titleStyle: { color: "blue" },
      });

      async function onChunk(blob: Blob, offset: number) {
        const numBytesWritten = await callRoute<SerializableObject, number>(
          endpoint,
          "/files/upload/write-object-bytes",
          {
            object_id: objectId,
            position: offset,
            data: await blobToBase64(blob),
          }
        );

        if (!Number.isInteger(numBytesWritten)) {
          throw new Error(`Invalid response from server: ${numBytesWritten}`);
        }

        if (numBytesWritten !== blob.size) {
          throw new Error(
            `Expected ${blob.size} bytes, wrote ${numBytesWritten}.`
          );
        }

        updateMessageById(progressBarId, (bar: ProgressMessage) => {
          (bar as ProgressBarMessage).current = offset + blob.size;
          return bar;
        });
      }

      await new FileStreamer(file, MAX_UPLOAD_CHUNK_SIZE, onChunk).run();

      addProgressMessage({
        kind: "string",
        text: `Successfully uploaded file to object ${objectId}`,
        color: "green",
      });
      addProgressMessage({
        kind: "string",
        text: `Creating document metadata...`,
      });

      const documentId = await callRoute<SerializableObject, string>(
        endpoint,
        "/documents/create",
        {
          title,
          author,
          description: description || null,
          object_id: objectId,
        }
      );

      addProgressMessage({
        kind: "string",
        text: `Created document with id ${documentId}`,
        color: "green",
      });

      addProgressMessage({
        kind: "string",
        text: "Preprocessing document...",
      });

      await callRoute<SerializableObject, string>(
        endpoint,
        "/documents/preprocess",
        {
          document_id: documentId,
        }
      );

      addProgressMessage({
        kind: "string",
        text: "Preprocessing complete.",
        color: "green",
      });
    } catch (err) {
      console.error(err);

      addProgressMessage({
        kind: "string",
        text: "Upload failed.",
        color: "red",
      });

      throw err;
    }
  }

  return (
    <>
      <Head>
        <title>Upload a Document</title>
        <meta
          name="description"
          content="Upload a document to be processed by the AI."
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
            // padding="1rem"
            height="5rem"
            lineHeight="5rem"
            textAlign="center"
            background={theme.colors.card.header.bg}
            color={theme.colors.card.header.text}
            borderRadius="1rem 1rem 0 0"
            boxShadow={`4px 4px 4px 0px ${theme.colors.card.body.shadow}`}
          >
            Upload a Document
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
              <input
                type="file"
                accept=".txt"
                {...register("file")}
                style={{ display: "none" }}
                onChange={(e) => handleFilePicker(e.target.files!)}
                ref={inputRef}
              />
              {errors.file && <P color="red">{errors.file.message}</P>}
              <Div
                onDrop={onDrop}
                onDragOver={onDragOver}
                onClick={onClickZone}
                cursor="pointer"
                width="auto"
                display="flex"
                alignItems="center"
                justifyContent="center"
                border="2px dashed black"
                borderRadius="0.5rem"
                padding="1rem"
                background="white"
              >
                {currentlySelectedFile ? (
                  <Div textAlign="center">
                    <P>{currentlySelectedFile.name}</P>
                    <P>
                      {(currentlySelectedFile.size / (1024 * 1024)).toFixed(2)}{" "}
                      MB
                    </P>
                  </Div>
                ) : (
                  <Div textAlign="center">
                    <P>Drag & drop a .txt file or click to browse</P>
                    <P>20 MB Maximum</P>
                    <P>
                      Supported Extensions:{" "}
                      {Object.values(ALLOWED_TYPES)
                        .flatMap((t) => t.extensions)
                        .map((ext) => `.${ext}`)
                        .join(", ")}
                    </P>
                  </Div>
                )}
              </Div>

              {/* Metadata inputs */}
              <Div
                display="flex"
                flexDirection="column"
                gap="0.5rem"
                width="100%"
              >
                <input
                  {...register("title")}
                  disabled={isSubmitting || isSubmitted}
                  placeholder="Title"
                  style={{
                    padding: "0.5rem",
                    border: "1px solid #ccc",
                    borderRadius: "0.25rem",
                  }}
                />
                {errors.title && <P color="red">{errors.title.message}</P>}

                <input
                  {...register("author")}
                  disabled={isSubmitting || isSubmitted}
                  placeholder="Author"
                  style={{
                    padding: "0.5rem",
                    border: "1px solid #ccc",
                    borderRadius: "0.25rem",
                  }}
                />
                {errors.author && <P color="red">{errors.author.message}</P>}

                <textarea
                  {...register("description")}
                  disabled={isSubmitting || isSubmitted}
                  rows={5}
                  placeholder="Description (optional)"
                  style={{
                    padding: "0.5rem",
                    border: "1px solid #ccc",
                    borderRadius: "0.25rem",
                  }}
                />
                {errors.description && (
                  <P color="red">{errors.description.message}</P>
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
                <MdCloudUpload />
                <Span>
                  {isSubmitting
                    ? "Uploading…"
                    : isSubmitSuccessful
                    ? "Upload Complete."
                    : isSubmitted && !isSubmitSuccessful
                    ? "Upload Failed."
                    : "Upload"}
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
              {(isSubmitSuccessful || (isSubmitted && !isSubmitSuccessful)) && (
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
                  Upload Another
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
        </Div>
      </Div>
    </>
  );
}
