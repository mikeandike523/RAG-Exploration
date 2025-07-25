import React, { forwardRef } from "react";
import { Div, P, DivProps } from "style-props-html";
import { TextMessage, ProgressBarMessage, ProgressMessage } from "./types";

interface LiveProgressViewerProps extends DivProps {
  progressMessages: Map<string, ProgressMessage>;
}

/** Renders a plain-text message */
function MessageText({ message}: { message: TextMessage }) {
  return (
    <Div
      width="100%"
      background={message.backgroundColor}
      color={message.color}
      fontWeight={message.fontWeight}
      fontStyle={message.fontStyle}
      fontSize={message.fontSize}
      padding="0.5rem"
      display="flex"
      flexDirection="column"
      alignItems="flex-start"
      gap="0.25rem"
    >
      {message.title && <P 
        background={message.titleStyle?.backgroundColor}
        color={message.titleStyle?.color}
        fontWeight={message.titleStyle?.fontWeight}
        fontStyle={message.titleStyle?.fontStyle}
        fontSize={message.titleStyle?.fontSize}
      >{message.title}</P>}
      <P whiteSpace="pre-wrap">{message.text}</P>
    </Div>
  );
}

/** Renders a progress‐bar message */
function ProgressBar({ message }: { message: ProgressBarMessage }) {
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
      gap="0.25rem"
    >
      <Div
        width="100%"
        background={message.titleStyle?.backgroundColor}
        color={message.titleStyle?.color}
        fontWeight={message.titleStyle?.fontWeight}
        fontStyle={message.titleStyle?.fontStyle}
        fontSize={message.titleStyle?.fontSize}
      >
        {message.title} — {percentText}
      </Div>
      <Div
        width="100%"
        background="#e0e0e0"
        borderRadius="0.25rem"
        height="1rem"
      >
        <Div
          width={widthPercent}
          background={message.titleStyle?.color}
          height="100%"
          borderRadius="0.25rem"
        />
      </Div>
    </Div>
  );
}

/**
 * The LiveProgressViewer component.
 * Accepts a Map of messages and a ref for auto‐scrolling.
 */
export default forwardRef<HTMLDivElement, LiveProgressViewerProps>(
  function LiveProgressViewer({ progressMessages, ...rest }, ref) {
    return (
      <Div
        transition="width 0.3s ease-in-out"
        ref={ref}
        overflowY="auto"
        padding="1rem"
        display="flex"
        flexDirection="column"
        gap="0.5rem"
        {...rest}
      >
        {[...progressMessages.entries()].map(([id, msg]) => (
          <Div
            key={id}
            background="white"
            padding="0.25rem"
            boxShadow="4px 4px 4px 0px rgba(0,0,0,0.1)"
            borderRadius="0.5rem"
          >
            {msg.kind === "string" ? (
              <MessageText message={msg} />
            ) : (
              <ProgressBar message={msg} />
            )}
          </Div>
        ))}
      </Div>
    );
  }
);

