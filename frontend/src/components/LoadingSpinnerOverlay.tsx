import { Div } from "style-props-html";
import { css, keyframes } from "@emotion/react";

const spinAnimation = keyframes`
    0% {
        transform: rotate(0deg);
    }
    100% {
        transform: rotate(360deg);
    }
`;

export interface LoadingSpinnerOverlayProps {
  size: string | number;
}

export default function LoadingSpinnerOverlay({
  size,
}: LoadingSpinnerOverlayProps) {
  const sizeString = typeof size === "number" ? `${size}px` : size;
  return (
    <Div
      position="absolute"
      top={0}
      left={0}
      right={0}
      bottom={0}
      display="flex"
      flexDirection="row"
      alignItems="center"
      justifyContent="center"
    >
      <Div
        transformOrigin="center"
        borderRadius="50%"
        border="2px solid blue"
        borderTop="2px solid transparent"
        width={sizeString}
        height={sizeString}
        css={css`
          animation: ${spinAnimation} 1s linear infinite;
        `}
      ></Div>
    </Div>
  );
}
