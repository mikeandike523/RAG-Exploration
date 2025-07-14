import Head from "next/head";
import { Div, H1, Li, P, Ul } from "style-props-html";
import { useState, useRef, DragEvent } from "react";

import theme from "@/themes/light";
import emojis from "@/utils/emojis";

const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20MB
const ALLOWED_TYPES = ["text/plain"]; // .txt files

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [isUploading, setIsUploading] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = (files: FileList) => {
    const selected = files[0];
    if (!selected) return;

    // Validate type
    if (!ALLOWED_TYPES.includes(selected.type)) {
      setError("Unsupported file type. Please upload a .txt file.");
      setFile(null);
      return;
    }

    // Validate size
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

  // Skeleton for file upload
  const uploadFile = async () => {
    if (!file) return;
    try {
      // TODO: implement upload logic, e.g.,
      // const formData = new FormData();
      // formData.append('file', file);
      // const res = await fetch('/api/upload', { method: 'POST', body: formData });
      // const result = await res.json();
      console.log("Uploading file...", file.name);
    } catch (err) {
      console.error("Upload failed", err);
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
            width="100%"
            padding="1rem"
            display="grid"
            gridTemplateColumns="auto 1fr"
          >
            <Div 
            
            transition="width 0.3s ease-in-out"
            width={
              isUploading? "auto" : "75vw"

            } display="flex" flexDirection="column" alignItems="center" justifyContent="center">
              {/* Hidden file input */}
              <input
                type="file"
                accept=".txt"
                ref={inputRef}
                style={{ display: "none" }}
                onChange={(e) => handleFiles(e.target.files!)}
              />

              {/* Drop zone */}
              <Div
                onDrop={onDrop}
                onDragOver={onDragOver}
                onClick={onClickZone}
                cursor="pointer"
                width="100%"
                display="flex"
                alignItems="center"
                justifyContent="center"
                borderRadius="0.5rem"
                background="white"
                padding="0.25rem"
                maxWidth="30em"
              >
                <Div
                  width="100%"
                  fontSize="1.25rem"
                  border="2px dashed black"
                  borderRadius="0.5rem"
                  padding="0.25rem"
                >
                  {file ? (
                    <div>
                      <p>{`Selected file: ${file.name}`}</p>
                      <p>{`Size: ${(file.size / (1024 * 1024)).toFixed(
                        2
                      )} MB`}</p>
                    </div>
                  ) : (
                    <Div width="100%" textAlign="center">
                      <P>Drag and drop a file here.</P>
                      <P>- or -</P>
                      <P>Click here to open file browser.</P>
                    </Div>
                  )}
                </Div>
              </Div>

              {error && (
                <p style={{ color: "red", marginTop: "1rem" }}>{error}</p>
              )}

              {/* File details and upload button */}
              {file && (
                <Div marginTop="1rem">
                  <button onClick={uploadFile}>Upload File</button>
                </Div>
              )}

              <Ul fontSize="1.25rem" marginTop="2rem">
                <Li>{`${emojis.bullet} 20MB Max`}</Li>
                <Li>{`${emojis.bullet} Supported Files:`}</Li>
                <Li>
                  <Ul marginLeft="1.25rem">
                    <Li>{`${emojis.bullet} Text Files (.txt)`}</Li>
                    <Li>{`${emojis.bullet} PDF Files (.pdf) (TODO)`}</Li>
                    <Li>{`${emojis.bullet} Word Files (.docx) (TODO)`}</Li>
                    <Li>{`${emojis.bullet} Open Office Files (.odt) (TODO)`}</Li>
                    <Li>{`${emojis.bullet} Rich Text Files (.rtf) (TODO)`}</Li>
                  </Ul>
                </Li>
              </Ul>
            </Div>
            <Div></Div>
          </Div>
        </Div>
      </Div>
    </>
  );
}
