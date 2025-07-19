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
import { ProgressBarMessage, ProgressMessage } from "@/components/live-progress-viewer/types";
import LiveProgressViewer from "@/components/live-progress-viewer/LiveProgressViewer";

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

export default function Upload() {
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadFinished, setUploadFinished] = useState(false);
  const [uploadFailed, setUploadFailed] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);

  const {
    progressMessages,
    containerRef: progressContainerRef,
    addProgressMessage,
    updateMessageById,
    // … other actions
  } = useLiveProgressViewer();

  const handleFiles = (files: FileList): void => {
    const selected = files[0];
    if (!selected) return;

    if (!selected.name.includes(".")) {
      setError("Invalid file name. Please include a valid file extension.");
      setFile(null);
      return;
    }

    if (
      !Object.values(ALLOWED_TYPES)
        .flatMap((t) => t.extensions)
        .includes(selected.name.split(".").pop() ?? "")
    ) {
      setError(
        `Unsupported file extension ${selected.name.split(".").pop() ?? ""})`
      );
      setFile(null);
      return;
    }

    if (!Object.keys(ALLOWED_TYPES).includes(selected.type)) {
      setError(`Unsupported file type ${selected.type}.`);
      setFile(null);
      return;
    }

    if (selected.size > MAX_FILE_SIZE) {
      setError("File is too large. Maximum allowed size is 20MB.");
      setFile(null);
      return;
    }

    setError(null);
    setFile(selected);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    handleFiles(e.dataTransfer.files);
  };

  const onDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  const onClickZone = () => {
    inputRef.current?.click();
  };

  async function uploadFile() {
    if (!file) return;
    try {
      setIsUploading(true);
      setUploadFinished(false);
      setUploadFailed(false);

      addProgressMessage({
        kind: "string",
        text: "Uploading...",
      });

      addProgressMessage({
        kind: "string",
        text: "Creating object...",
      });

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
          throw new Error(
            `
Invalid response from server.
Expected an integer.
Recieved type ${typeof numBytesWritten},
value ${numBytesWritten} instead of an integer.
`.trim()
          );
        }

        // Note, our custom `FileStreamer` class
        // already manages blob size to be exactly as needed,
        // even when approach the end of the file and having
        // incomplete chunks

        if (numBytesWritten !== blob.size) {
          throw new Error(
            `
Invalid response from server.

Expected to write exactly ${blob.size} bytes,
Wrote ${numBytesWritten} bytes instead of ${blob.size}.
`
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

      setUploadFinished(true);
      setUploadFailed(false);
    } catch (err) {
      console.error(err);
      addProgressMessage({
        kind: "string",
        text: "Upload failed.",
        color: "red",
      });
      setUploadFailed(true);
      setUploadFinished(false);
    } finally {
      setIsUploading(false);
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
            padding="1rem"
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
              justifyContent="center"
              gap="0.5rem"
              padding="1rem"
              width={
                isUploading || uploadFinished || uploadFailed ? "30vw" : "75vw"
              }
            >
              <input
                type="file"
                accept=".txt"
                ref={inputRef}
                style={{ display: "none" }}
                onChange={(e) => handleFiles(e.target.files!)}
              />
              <Div
                onDrop={onDrop}
                onDragOver={onDragOver}
                onClick={onClickZone}
                cursor="pointer"
                width="100%"
                maxWidth="30em"
                display="flex"
                alignItems="center"
                justifyContent="center"
                border="2px dashed black"
                borderRadius="0.5rem"
                padding="1rem"
                background="white"
              >
                {file ? (
                  <Div textAlign="center">
                    <P>{file.name}</P>
                    <P>{(file.size / (1024 * 1024)).toFixed(2)} MB</P>
                  </Div>
                ) : (
                  <Div textAlign="center">
                    <P>Drag & drop a .txt file or click to browse</P>
                    <P>20 MB Maximum</P>
                    <P>
                      {Object.values(ALLOWED_TYPES)
                        .flatMap((t) => t.extensions)
                        .map((ext) => `.${ext}`)
                        .join(", ")}
                    </P>
                  </Div>
                )}
              </Div>
              {file && (
                <Button
                  onClick={uploadFile}
                  disabled={isUploading || uploadFinished || uploadFailed}
                  display="flex"
                  alignItems="center"
                  gap="0.5rem"
                  padding="0.5rem 1rem"
                  borderRadius="0.5rem"
                  position="relative"
                >
                  <MdCloudUpload />
                  <Span>
                    {isUploading
                      ? "Uploading..."
                      : uploadFailed
                      ? "Upload Failed."
                      : uploadFinished
                      ? "Upload Complete."
                      : "Upload"}
                  </Span>
                  {isUploading && <LoadingSpinnerOverlay size="1rem" />}
                </Button>
              )}
              {error && <P color="red">{error}</P>}
            </Div>
            <Div
              width={
                isUploading || uploadFinished || uploadFailed ? "45vw" : "0"
              }
              transition="width 0.3s ease-in-out"
            >
              <LiveProgressViewer
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
