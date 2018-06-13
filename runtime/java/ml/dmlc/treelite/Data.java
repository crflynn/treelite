
package ml.dmlc.treelite;

public interface Data {
  public void setFValue(float val);
  public void setQValue(int val);
  public void setMissing();
  public boolean isMissing();
  public float getFValue();
  public int getQValue();
}
