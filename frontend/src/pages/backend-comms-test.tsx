import { Div, H1 } from "style-props-html";
import { useState } from "react";

import { LiveRouteError } from "@/utils/live-rpc";

export default function BackendCommsTest() {
  // Test #1 - Task "version"
  const [versionTaskResult, setVersionTaskResult] = useState<
    string | undefined
  >(undefined);
  const [versionTaskError, setVersionTaskError] = useState<
    LiveRouteError | undefined
  >(undefined);

  return (
    <Div
      width="100%"
      height="100%"
      display="flex"
      flexDirection="column"
      alignItems="center"
      justifyContent="flex-start"
      padding="0.5rem"
      gap="0.5rem"
    >
      <H1 fontSize="1.5rem">Backend Comms Test</H1>
      <Div
        width="100%"
        border="2px solid black"
        padding="0.25rem"
        display="flex"
        flexDirection="row"
        alignItems="flex-start"
        justifyContent="flex-start"
      ></Div>
    </Div>
  );
}
