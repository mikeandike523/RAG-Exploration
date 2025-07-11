/**
 * serialization.ts
 *
 * A collection of types and utilities for serializing and de-serializing using the JSON format.
 */

/**
 * The set of primitive types that can be serialized losslessly by JSON
 */
export type SerializablePrimitive = string | number | boolean | null;

/**
 * The types of object keys that can be serialized losslessly by JSON
 */
export type SerializableKey = string | number;

/**
 * The types of objects that can be serialized losslessly by JSON
 *
 * Supports JSON root objects of: primitive, object/record, and array
 */
export type SerializableObject =
  | SerializablePrimitive
  | SerializableObject[]
  | { [key: SerializableKey]: SerializableObject };

/**
 * A serializable object that is an object (i.e. mapping) type at the top level (JSON root object/record)
 */
export type SerializableRecord = {
  [key: SerializableKey]: SerializableObject;
};

/**
 * A mapping of serializable keys to PRIMITIVE serializable values
 * Very useful for operations related to sql databases
 */
export type FlatSerializableRecord = {
  [key: SerializableKey]: SerializablePrimitive;
};

/**
 * A serializable object that is an array (i.e. list) type at the top level (JSON root object [])
 */
export type SerializableArray = Array<SerializableObject>;

/**
 * Determines if a given value is a serializable primitive.
 * @param value - The value to check.
 * @returns - An `is` type guard for `SerializablePrimitive`.
 */
export function isSerializablePrimitive(
  value: unknown,
): value is SerializablePrimitive {
  return (
    typeof value === 'string' ||
    typeof value === 'number' ||
    typeof value === 'boolean' ||
    value === null
  );
}

/**
 *
 * Converts any value to its nearest JSON serializable representation.
 *
 * Behaviors:
 *
 * 1. If the top level value is not serializable, throws an error
 * 2. Otherwise, values in a tree that are replaced with null
 *    This was a difficult choice but its useful when serializing arrays
 *    Its basically a silent error condition, which is generally sub-optimal
 *    but it is sufficient for this project
 * 3. Circular references are serialized to null, similar to other non-serializable values
 *
 * WARNING: Does NOT work with more complex data storage like maps or sets, these will simply by serialized to null, or to an object containing no properties or a few non-useful properties
 *
 *
 * @param value - A value to convert to the nearest JSON serializable object representation
 * @param enumerableOnly - Whether to include only enumerable properties in the JSON representation. Useful for things such as arrays with broken prototype chain. Simply controls whether `Object.getOwnPropertyNames` or `object.keys` is used.
 */
export function toNearestSerializableObject(
  value: unknown,
  enumerableOnly: boolean = true,
  skipUndefinedProperties=true,
): SerializableObject {
  if (!isSerializablePrimitive(value) && typeof value !== 'object') {
    throw new Error(`Provided value is not serializable at the top level`);
  }
  const seenItems = new Set<object>();
  const recursion = (value: unknown): SerializableObject => {
    if (isSerializablePrimitive(value)) {
      return value;
    }
    if (typeof value === 'object') {
      if (seenItems.has(value as object)) {
        return null;
      }
      seenItems.add(value as object);
      if (Array.isArray(value)) {
        return value.map((item) => recursion(item));
      } else {
        const result: {
          [key: SerializableKey]: SerializableObject;
        } = {};
        const keys = enumerableOnly
          ? Object.keys(value as object)
          : Object.getOwnPropertyNames(value);
        for (const key of keys) {
          const resultItem = recursion((value as object)[key as keyof object]);
          if(typeof resultItem === "undefined"){
            if(skipUndefinedProperties){
              continue
            }else{
              result[key] = null;
            }
          }else{
            result[key] = resultItem;
          }
        }
        return result;
      }
    }
    return null;
  };
  return recursion(value);
}

export function deepCopySerializableObject<T extends SerializableObject>(
  obj: T,
): T {
  return JSON.parse(JSON.stringify(obj));
}

export type ParseResult<T extends SerializableObject> =
  | { parsable: true; data: T }
  | { parsable: false; text: string; error: unknown };

export function safeParse<T extends SerializableObject>(
  potentialJSON: string,
): ParseResult<T> {
  try {
    return {
      parsable: true,
      data: JSON.parse(potentialJSON),
    };
  } catch (e) {
    return {
      parsable: false,
      text: potentialJSON,
      error: e,
    };
  }
}