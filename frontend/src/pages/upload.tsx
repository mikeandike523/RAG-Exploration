import Head from "next/head";
import React, {
  ChangeEvent,
  DragEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import { MdCloudUpload } from "react-icons/md";
import {
  Button,
  Div,
  H1,
  Input,
  Label,
  P,
  Span,
  Textarea,
} from "style-props-html";
import { v4 as uuidv4 } from "uuid";

import LoadingSpinnerOverlay from "@/components/LoadingSpinnerOverlay";
import theme from "@/themes/light";
import { callRoute } from "@/utils/rpc";

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

type TextMessage = {
  kind: "string";
  text: string;
  backgroundColor?: string;
  color?: string;
  fontWeight?: "bold" | "normal";
  fontStyle?: "italic" | "normal";
  fontSize?: string;
};

type ProgressBarMessage = {
  kind: "progressBar";
  title: string;
  unit?: string;
  precision?: number;
  showAsPercent: boolean;
  max: number;
  current: number;
  titleStyle: {
    backgroundColor?: string;
    color?: string;
    fontWeight?: "bold" | "normal";
    fontStyle?: "italic" | "normal";
    fontSize?: string;
  };
};

type ProgressMessage = TextMessage | ProgressBarMessage;

const MessageText: React.FC<{ message: TextMessage }> = ({ message }) => (
  <Div
    width="100%"
    background={message.backgroundColor}
    color={message.color}
    fontWeight={message.fontWeight}
    fontStyle={message.fontStyle}
    fontSize={message.fontSize}
    padding="0.5rem"
  >
    <P>{message.text}</P>
  </Div>
);

const ProgressBar: React.FC<{ message: ProgressBarMessage }> = ({
  message,
}) => {
  const percentText = message.showAsPercent
    ? ((message.current / message.max) * 100).toFixed(message.precision ?? 0) +
      "%"
    : message.current.toFixed(message.precision ?? 0) + (message.unit || "");
  const widthPercent = ((message.current / message.max) * 100).toFixed(2) + "%";

  return (
    <Div
      width="100%"
      padding="0.5rem"
      display="flex"
      flexDirection="column"
      alignItems="flex-start"
      justifyContent="flex-start"
      gap="0.25rem"
    >
      <Div
        width="100%"
        background={message.titleStyle.backgroundColor}
        color={message.titleStyle.color}
        fontWeight={message.titleStyle.fontWeight}
        fontStyle={message.titleStyle.fontStyle}
        fontSize={message.titleStyle.fontSize}
      >
        {message.title} - {percentText}
      </Div>
      <Div
        width="100%"
        background="#e0e0e0"
        borderRadius="0.25rem"
        height="1rem"
      >
        <Div
          width={widthPercent}
          background={message.titleStyle.color}
          height="100%"
          borderRadius="0.25rem"
        />
      </Div>
    </Div>
  );
};

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadFinished, setUploadFinished] = useState(false);
  const [uploadFailed, setUploadFailed] = useState(false);
  const [progressMessages, setProgressMessages] = useState<
    Map<string, ProgressMessage>
  >(new Map());
  const [documentTitle, setDocumentTitle] = useState("");
  const [documentAuthor, setDocumentAuthor] = useState("");
  const [documentDescription, setDocumentDescription] = useState("");
  const [formErrorDocumentTitle, setFormErrorDocumentTitle] = useState<
    string | null
  >(null);
  const [formErrorDocumentAuthor, setFormErrorDocumentAuthor] = useState<
    string | null
  >(null);
  const [formErrorDocumentDescription, setFormErrorDocumentDescription] =
    useState<string | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const progressContainerRef = useRef<HTMLDivElement>(null);

  const scrollProgressContainerToBottom = () => {
    const container = progressContainerRef.current;
    if (container) {
      container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
    }
  };

  useEffect(() => {
    scrollProgressContainerToBottom();
  }, [progressMessages.size]);

  const clearProgressMessages = (): void => {
    setProgressMessages(() => new Map());
  };

  const addProgressMessage = (message: ProgressMessage): string => {
    const id = uuidv4();
    setProgressMessages((prev) => {
      const next = new Map(prev);
      next.set(id, message);
      return next;
    });
    return id;
  };

  const deleteProgressMessageById = (id: string): void => {
    setProgressMessages((prev) => {
      const next = new Map(prev);
      next.delete(id);
      return next;
    });
  };

  const replaceMessageById = (
    id: string,
    newMessage: ProgressMessage
  ): void => {
    setProgressMessages((prev) => {
      const next = new Map(prev);
      next.set(id, newMessage);
      return next;
    });
  };

  const updateMessageById = (
    id: string,
    callback: (previous: ProgressMessage) => ProgressMessage
  ): void => {
    setProgressMessages((prev) => {
      const next = new Map(prev);
      const existing = next.get(id);
      if (!existing) return prev;
      next.set(id, callback(existing));
      return next;
    });
  };

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
    setDocumentTitle("");
    setDocumentAuthor("");
    setDocumentDescription("");
    setFormErrorDocumentTitle(null);
    setFormErrorDocumentAuthor(null);
    setFormErrorDocumentDescription(null);
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

  // Skeleton for file upload
  const uploadFile = async (): Promise<void> => {
    if (!file) return;
    setFormErrorDocumentAuthor(null);
    setFormErrorDocumentDescription(null);
    setFormErrorDocumentTitle(null);

    let hasFormErrors = false;

    if(!documentTitle.trim()) {
      setFormErrorDocumentTitle("Title is required");
      hasFormErrors = true;
    }

    if(!documentAuthor.trim()) {
      setFormErrorDocumentAuthor("Author is required");
      hasFormErrors = true;
    }

    if(hasFormErrors){
      return
    }


    try {
      setIsUploading(true);
      setUploadFinished(false);
      setUploadFailed(false);

      addProgressMessage({
        kind: "string",
        text: "Uploading...",
      });

      // Example progress updates:
      const progressBarId = addProgressMessage({
        kind: "progressBar",
        title: "Uploading",
        showAsPercent: true,
        max: file.size,
        current: 0,
        precision: 0,
        titleStyle: { color: "blue" },
      });
      // Simulate progress:
      // let uploaded = 0;
      // const chunk = file.size / 10;
      // while (uploaded < file.size) {
      //   await new Promise((r) => setTimeout(r, 200));
      //   uploaded = Math.min(uploaded + chunk, file.size);
      //   updateMessageById(id, (m) => ({
      //     ...(m as ProgressBarMessage),
      //     current: uploaded,
      //   }));
      // }

      addProgressMessage({
        kind: "string",
        text: "Creating object...",
      });

      const objectId = await callRoute(endpoint, "/files/upload/new-object", {
        name: file.name,
        mime_type: file.type,
        size: file.size,
      });

      addProgressMessage({
        kind: "string",
        text: `Created object with id ${objectId}`,
      });

      const reader = file.stream().getReader();
      let offset = 0;

      async function onChunk(chunkBlob: Blob, offset: number) {}

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunkBlob = new Blob([value]);
        await onChunk(chunkBlob, offset);

        offset += value?.length ?? 0;
      }
      addProgressMessage({
        kind: "string",
        text: "Upload complete!",
        color: "green",
      });
      setUploadFinished(true);
      setUploadFailed(false);
    } catch (err) {
      console.error("Upload failed", err);
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
  };

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
                <Div width="100%" maxWidth="30em">
                  <Label width="100%">
                    <P>Title*:</P>
                    <Input
                      disabled={isUploading || uploadFinished || uploadFailed}
                      width="100%"
                      type="text"
                      value={documentTitle}
                      onChange={(e: ChangeEvent<HTMLInputElement>) =>
                        setDocumentTitle(e.target.value)
                      }
                    />
                    {formErrorDocumentTitle && (
                      <P color="red">{formErrorDocumentTitle}</P>
                    )}
                  </Label>
                  <Label width="100%">
                    <P>Author*:</P>
                    <Input
                      disabled={isUploading || uploadFinished || uploadFailed}
                      width="100%"
                      type="text"
                      value={documentAuthor}
                      onChange={(e: ChangeEvent<HTMLInputElement>) =>
                        setDocumentAuthor(e.target.value)
                      }
                    />
                  </Label>
                  <Label width="100%">
                    <P>Description*:</P>
                    <Textarea
                      value={documentDescription}
                      onChange={(e: ChangeEvent<HTMLTextAreaElement>) => {
                        setDocumentDescription(e.target.value);
                      }}
                      disabled={isUploading || uploadFinished || uploadFailed}
                      width="100%"
                      rows={3}
                    />
                  </Label>
                </Div>
              )}
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
              ref={progressContainerRef}
              overflowY="auto"
              padding="1rem"
              display="flex"
              flexDirection="column"
              gap="0.5rem"
            >
              {[...progressMessages.entries()].map(([id, msg]) => (
                <Div
                  background="white"
                  padding="0.25rem"
                  boxShadow={`4px 4px 4px 0px ${theme.colors.card.body.shadow}`}
                  borderRadius="0.5rem"
                >
                  {msg.kind === "string" ? (
                    <MessageText key={id} message={msg} />
                  ) : (
                    <ProgressBar key={id} message={msg} />
                  )}
                </Div>
              ))}
            </Div>
          </Div>
        </Div>
      </Div>
    </>
  );
}
