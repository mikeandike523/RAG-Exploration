import {
  SerializableObject,
  toNearestSerializableObject,
  safeParse,
} from "./serialization";
import { io, Socket } from "socket.io-client";

export type SuccessResponse<T extends SerializableObject | void = void> = {
  result: T;
};

export type ErrorResponse<T extends SerializableObject | void = void> = {
  message: string;
  cause?: T;
};

export type FatalErrorResponse<T extends SerializableObject | void = void> = {
  message: string;
  cause?: T;
};

export type ProgressResponse = {
  /**
   * In the rare case a task wants to track multiple progress bars
   */
  name?: string;
  current: number;
  total: number;
};

export type UpdateResponse<T extends SerializableObject | void = void> = {
  message: string;
  extra?: T;
};

export type WarningResponse<T extends SerializableObject | void = void> = {
  message: string;
  extra?: T;
};

export class RPCerror<
  T extends SerializableObject | void = void
> extends Error {
  constructor(message: string, cause?: T) {
    super(message);
    this.name = "RPCError";
    this.cause = cause;
  }
}

/**
 * Note, onSuccess is not included, as the function returns on success
 */
export interface LiveRouteHandlers {
  onError?: <T extends SerializableObject | void = void>(
    error: ErrorResponse<T>
  ) => void;
  onFatalError?: <T extends SerializableObject | void = void>(
    error: FatalErrorResponse<T>
  ) => void;
  onWarning?: <T extends SerializableObject | void = void>(
    warning: WarningResponse<T>
  ) => void;
  onProgress?: (progress: ProgressResponse) => void;
  onUpdate?: <T extends SerializableObject | void = void>(
    update: UpdateResponse<T>
  ) => void;
}

export async function callRoute<
  TArgs extends SerializableObject | void = void,
  TRet extends SerializableObject | void = void
>(
  endpoint: string,
  route: string,
  args: TArgs,
  timeout?: number
): Promise<TRet> {
  try {
    const response = await fetch(endpoint.replace(/\/+$/g, "") + "/run", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ task: route, args }),
      // signal:
      //   typeof AbortSignal === "undefined"
      //     ? undefined
      //     : timeout
      //     ? AbortSignal.timeout(timeout)
      //     : undefined,
    });
    const responseBody = await response.text();
    const responseBodyAsJSON = safeParse(responseBody);
    if (!response.ok) {
      throw new RPCerror(
        {
          400: "Invalid Route Name or Arguments",
          401: "Not Authenticated",
          403: "Insufficient Permission",
          500: "Unknown Backend Server Error",
          502: "Bad Gateway (Backend server may be off.)",
          404: "Endpoint Not Found (Check endpoint URL.)",
        }[response.status] ?? "Unkown Error",
        toNearestSerializableObject(
          {
            status: response.status,
            data: responseBodyAsJSON.parsable
              ? responseBodyAsJSON.data
              : undefined,
            body: responseBody,
          },
          false,
          true
        )
      );
    }
    if (!responseBodyAsJSON.parsable) {
      throw new RPCerror(
        "Server responded with success http code, but response body was not valid json. This is not expected."
      );
    }
    return responseBodyAsJSON.data as TRet;
  } catch (e) {
    if (e instanceof RPCerror) {
      throw e;
    } else {
      throw new RPCerror(
        "An unexpected error occurred",
        toNearestSerializableObject(e, false, true)
      );
    }
  }
}

/**
 *
 * @param endpoint - The path to the "begin" endpoint.
 * You should include the "/begin" in the URL. This is for future proofing, for instance if
 * we implement multiple api versions
 * @param route
 * @param args
 * @param handlers
 * @param timeout - Time in milliseconds for the request to timeout.
 * @returns
 */
export async function callLiveRoute<
  TArgs extends SerializableObject | void = void,
  TRet extends SerializableObject | void = void
>(
  endpoint: string,
  route: string,
  args: TArgs,
  handlers: LiveRouteHandlers,
  timeout?: number
): Promise<TRet> {
  try {
    const taskBeginResponse = await fetch(
      endpoint.replace(/\/+$/g, "") + "/begin",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ task: route, args }),
        // signal:
        //   typeof AbortSignal === "undefined"
        //     ? undefined
        //     : timeout
        //     ? AbortSignal.timeout(timeout)
        //     : undefined,
      }
    );
    const responseBody = await taskBeginResponse.text();
    const responseBodyAsJSON = safeParse(responseBody);
    if (!taskBeginResponse.ok) {
      throw new RPCerror(
        {
          400: "Invalid Route Name or Arguments",
          401: "Not Authenticated",
          403: "Insufficient Permission",
          500: "Unknown Backend Server Error",
          502: "Bad Gateway (Backend server may be off.)",
          404: "Endpoint Not Found (Check endpoint URL.)",
        }[taskBeginResponse.status] ?? "Unkown Error",
        toNearestSerializableObject(
          {
            status: taskBeginResponse.status,
            data: responseBodyAsJSON.parsable
              ? responseBodyAsJSON.data
              : undefined,
            body: responseBody,
          },
          false,
          true
        )
      );
    }
    if (!responseBodyAsJSON.parsable) {
      throw new RPCerror(
        "Server responded with success http code, but response body was not valid json. This is not expected."
      );
    }
    const { task_id } = responseBodyAsJSON.data as {
      task_id: string;
    };
    return await new Promise((resolve, reject) => {

      const url = new URL(endpoint);

      const socketBase = url.origin; // e.g. "http://localhost:5050"

      // now point socket.io at port 5050
      const socket: Socket = io(socketBase, {
        path: "/socket.io", // only if your server uses the default path
        // transports: ["websocket"],               // optional: force WebSocket
      });

      socket.on("connect", () => {
        socket.emit("join", { task_id });
      });

      socket.on("progress", (data: ProgressResponse) => {
        handlers.onProgress?.(data);
      });
      socket.on(
        "warning",
        (data: WarningResponse<SerializableObject | void>) => {
          handlers.onWarning?.(data);
        }
      );
      socket.on("update", (data: UpdateResponse<SerializableObject | void>) => {
        handlers.onUpdate?.(data);
      });
      socket.on("error", (data: ErrorResponse<SerializableObject | void>) => {
        handlers.onError?.(data);
      });
      socket.on(
        "fatal_error",
        (data: FatalErrorResponse<SerializableObject | void>) => {
          handlers.onFatalError?.(data);
          socket.disconnect();
          reject(new Error(data.message));
        }
      );
      socket.on(
        "success",
        (data: SuccessResponse<SerializableObject | void>) => {
          socket.disconnect();
          resolve(data.result as TRet);
        }
      );
    });
  } catch (e) {
    if (e instanceof RPCerror) {
      throw e;
    } else {
      throw new RPCerror(
        "An unexpected error occurred",
        toNearestSerializableObject(e, false, true)
      );
    }
  }
}
