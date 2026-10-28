"use client";

import { useRef, useState } from "react";

import { formatNumericDate, parseArgentineDate } from "../../lib/format-date";

type DateFieldProps = {
  name: string;
  label: string;
  defaultValue?: string | null;
  required?: boolean;
  error?: string;
};

export function DateField({
  name,
  label,
  defaultValue,
  required = false,
  error,
}: DateFieldProps) {
  const dateInputId = `date-field-${name}`;
  const dateHintId = `${dateInputId}-hint`;
  const visibleDateInputRef = useRef<HTMLInputElement>(null);
  const datePickerRef = useRef<HTMLInputElement>(null);
  const [displayValue, setDisplayValue] = useState(
    formatNumericDate(defaultValue),
  );
  const [pickerValue, setPickerValue] = useState(defaultValue ?? "");
  const [formatError, setFormatError] = useState("");
  const visibleError = error || formatError;

  function validateInput(input: HTMLInputElement) {
    const value = input.value.trim();
    const message =
      value === "" && required
        ? "Completá la fecha."
        : value !== "" && !parseArgentineDate(value)
          ? "Ingresá una fecha válida con el formato DD/MM/AAAA."
          : "";
    input.setCustomValidity(message);
    setFormatError(message);
  }

  function openNativeDatePicker() {
    const datePicker = datePickerRef.current;
    if (!datePicker) return;

    if (typeof datePicker.showPicker === "function") {
      datePicker.showPicker();
    } else {
      datePicker.click();
    }
  }

  return (
    <div className="admin-date-field">
      <label htmlFor={dateInputId}>{label}</label>
      <div className="admin-date-field-control">
        <input
          ref={visibleDateInputRef}
          id={dateInputId}
          name={name}
          type="text"
          inputMode="numeric"
          autoComplete="off"
          placeholder="DD/MM/AAAA"
          maxLength={10}
          pattern="[0-9]{2}/[0-9]{2}/[0-9]{4}"
          required={required}
          value={displayValue}
          aria-invalid={Boolean(visibleError)}
          aria-describedby={visibleError ? dateHintId : undefined}
          onChange={(event) => {
            event.currentTarget.setCustomValidity("");
            const nextValue = event.currentTarget.value;
            setDisplayValue(nextValue);
            setPickerValue(parseArgentineDate(nextValue) ?? "");
            setFormatError("");
          }}
          onBlur={(event) => validateInput(event.currentTarget)}
          onInvalid={(event) => validateInput(event.currentTarget)}
        />
        <button
          className="admin-date-field-picker-button"
          type="button"
          aria-label={`Elegir ${label.toLocaleLowerCase("es-AR")} en calendario`}
          onClick={openNativeDatePicker}
        >
          Calendario
        </button>
        <input
          ref={datePickerRef}
          className="admin-date-field-native-picker"
          type="date"
          value={pickerValue}
          tabIndex={-1}
          aria-hidden="true"
          onChange={(event) => {
            const isoDate = event.currentTarget.value;
            setPickerValue(isoDate);
            setDisplayValue(formatNumericDate(isoDate));
            visibleDateInputRef.current?.setCustomValidity("");
            setFormatError("");
          }}
        />
      </div>
      {visibleError ? (
        <small id={dateHintId} role="alert">
          {visibleError}
        </small>
      ) : null}
    </div>
  );
}
