package mob;

import android.os.Environment;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.Charset;
import java.text.SimpleDateFormat;
import java.util.Arrays;
import java.util.concurrent.LinkedBlockingQueue;

public class Logger extends Thread {
  private static final ThreadLocal<Object> PARAMETER_BUFFER =
      new ThreadLocal<>();
  private static final LinkedBlockingQueue<String> QUEUE =
      new LinkedBlockingQueue<>();
  private static final SimpleDateFormat TIME_FORMAT1 =
      new SimpleDateFormat("HH:mm:ss.SSS");
  private static final SimpleDateFormat TIME_FORMAT2 =
      new SimpleDateFormat("yyyyMMddHHmmssSSS");

  static { new Logger().start(); }

  public Logger() { setDaemon(true); }

  public static void logstring(Object obj) {
    String stringRep = y(obj);
    String escaped = EscapeStrings(stringRep);
    z(escaped);
  }

  public static String EscapeStrings(String input) {
    return input.replace("\\", "\\\\")
        .replace("\t", "\\t")
        .replace("\b", "\\b")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\f", "\\f")
        .replace("'", "\\'")
        .replace("\"", "\\\"");
  }

  private static String y(Object obj) {
    if (obj == null)
      return "null";

    Class<?> cls = obj.getClass();
    if (cls.isArray()) {
      if (cls == byte[].class)
        return Arrays.toString((byte[])obj);
      if (cls == short[].class)
        return Arrays.toString((short[])obj);
      if (cls == int[].class)
        return Arrays.toString((int[])obj);
      if (cls == long[].class)
        return Arrays.toString((long[])obj);
      if (cls == char[].class)
        return Arrays.toString((char[])obj);
      if (cls == float[].class)
        return Arrays.toString((float[])obj);
      if (cls == double[].class)
        return Arrays.toString((double[])obj);
      if (cls == boolean[].class)
        return Arrays.toString((boolean[])obj);
      return Arrays.deepToString((Object[])obj);
    }
    return obj.toString();
  }

  private static void z(String message) {
    String template = "{\n\"[LOCATION]\"\n\"[RESULT]\"\n}\n";
    long currentTime = System.currentTimeMillis();

    // Replace time if needed
    if (template.contains("[TIME]")) {
      template = template.replace("[TIME]", TIME_FORMAT1.format(currentTime));
    }

    // Get caller information
    StackTraceElement[] stackTrace = new Throwable().getStackTrace();
    StackTraceElement caller = stackTrace[2];

    // Build location string
    String fileName =
        caller.getFileName() != null ? caller.getFileName() : "Unknown Source";
    int lineNumber = caller.getLineNumber();
    String location = lineNumber >= 0 ? fileName + ":" + lineNumber : fileName;

    // Build final message
    String output = template.replace("[RESULT]", message)
                        .replace("[CLASS]", caller.getClassName())
                        .replace("[METHOD]", caller.getMethodName())
                        .replace("[LOCATION]", location);

    QUEUE.offer(output);
  }

  @Override
  public void run() {
    FileOutputStream outputStream = null;
    String path =
        "[SDCARD]/MT2/dictionary/[PACKAGE]-[TIME].mtd"
            .replace("[SDCARD]",
                     Environment.getExternalStorageDirectory().getPath())
            .replace("[PACKAGE]", "MOBPKG")
            .replace("[TIME]", TIME_FORMAT2.format(System.currentTimeMillis()))
            .replace('\\', '/')
            .replace("//", "/");

    // Try primary location
    try {
      File file = new File(path);
      File parent = file.getParentFile();
      if (parent != null)
        parent.mkdirs();
      outputStream = new FileOutputStream(file, true);
    } catch (IOException e) {
      e.printStackTrace();
    }

    // Fallback to app data directory
    if (outputStream == null) {
      try {
        File fallbackDir = new File("/data/data/MOBPKG/dictionary");
        fallbackDir.mkdirs();
        File fallbackFile = new File(
            fallbackDir,
            TIME_FORMAT2.format(System.currentTimeMillis()) + ".mtd");
        outputStream = new FileOutputStream(fallbackFile);
      } catch (IOException e) {
        e.printStackTrace();
      }
    }

    // Continuous writing loop
    Charset charset = Charset.defaultCharset();
    try {
      while (true) {
        String message = QUEUE.take();
        outputStream.write(message.getBytes(charset));
        if (QUEUE.isEmpty())
          outputStream.flush();
      }
    } catch (Exception e) {
      throw new RuntimeException(e);
    }
  }
}
